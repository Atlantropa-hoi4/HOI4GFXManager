"""
HOI4 GFX 통합 관리 도구 (전문가 버전 + 드래그 앤 드롭)

필요한 라이브러리 설치:
pip install PyQt6 Pillow Pillow-DDS-Extended

전문가 기능:
- 완전한 GFX 편집 및 관리
- 안전한 삭제 및 리팩토링
- 일괄 임포트 및 프로젝트 관리
- 다크 모드 및 외부 편집기 연동
- 상세한 분석 리포트 및 내보내기
- 드래그 앤 드롭으로 이미지 파일 간편 추가
"""

import sys
import os
import re
import json
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QListWidget, QLabel, 
                            QFileDialog, QMessageBox, QSplitter, QTabWidget,
                            QLineEdit, QCheckBox, QTextEdit, QListWidgetItem,
                            QGroupBox, QProgressBar, QDialog, QFormLayout,
                            QComboBox, QSpinBox, QDialogButtonBox, QTreeWidget,
                            QTreeWidgetItem, QMenu, QMenuBar, QStatusBar,
                            QToolBar, QScrollArea, QFrame, QRadioButton)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSettings, QUrl, QMimeData
from PyQt6.QtGui import QPixmap, QColor, QAction, QIcon, QPalette, QDragEnterEvent, QDropEvent
from PIL import Image
import cv2
import numpy as np
try:
    from PIL import DdsImagePlugin
except ImportError:
    print("Warning: DDS plugin not available. DDS files cannot be opened.")

# GUI 프리뷰어 import
from gui_previewer import GUIPreviewWidget


class ImageConverter:
    """이미지 일괄 변환 클래스"""
    
    # DDS 포맷 옵션
    DDS_FORMATS = {
        'B8G8R8A8 (Linear, A8R8G8B8)': 'RGBA',  # 기본 권장 포맷
        'DXT1 (BC1)': 'DXT1',                   # 알파 없는 압축
        'DXT3 (BC2)': 'DXT3',                   # 알파 있는 압축 (sharp alpha)
        'DXT5 (BC3)': 'DXT5',                   # 알파 있는 압축 (smooth alpha)
        'BC7': 'BC7',                           # 최신 고품질 압축
        'R8G8B8': 'RGB',                        # 24비트 RGB
        'R8G8B8A8': 'RGBA'                      # 32비트 RGBA
    }
    
    def __init__(self):
        self.supported_input = ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tga']
        self.supported_output = ['.png', '.jpg', '.jpeg', '.bmp', '.dds']
    
    def convert_image(self, input_path, output_path, output_format='PNG', dds_format='RGBA', quality=95):
        """단일 이미지 변환"""
        try:
            # 이미지 로드
            with Image.open(input_path) as img:
                # 알파 채널 처리
                if img.mode in ('RGBA', 'LA') or 'transparency' in img.info:
                    # 알파 채널이 있는 경우
                    if output_format.upper() == 'DDS':
                        # DDS는 알파 채널 유지
                        if img.mode != 'RGBA':
                            img = img.convert('RGBA')
                    elif output_format.upper() in ['JPG', 'JPEG']:
                        # JPEG는 알파 채널 제거하고 흰 배경 합성
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'RGBA':
                            background.paste(img, mask=img.split()[3])  # 알파 채널로 마스크
                        else:
                            background.paste(img)
                        img = background
                    else:
                        # PNG, BMP 등은 알파 채널 유지
                        if img.mode != 'RGBA':
                            img = img.convert('RGBA')
                else:
                    # 알파 채널이 없는 경우
                    if output_format.upper() == 'DDS' and dds_format in ['RGBA', 'DXT3', 'DXT5']:
                        # DDS RGBA 포맷인 경우 알파 채널 추가
                        img = img.convert('RGBA')
                    elif output_format.upper() in ['JPG', 'JPEG']:
                        img = img.convert('RGB')
                
                # 포맷별 저장
                if output_format.upper() == 'DDS':
                    self._save_as_dds(img, output_path, dds_format)
                else:
                    save_kwargs = {}
                    if output_format.upper() in ['JPG', 'JPEG']:
                        save_kwargs['quality'] = quality
                        save_kwargs['optimize'] = True
                    elif output_format.upper() == 'PNG':
                        save_kwargs['optimize'] = True
                    
                    img.save(output_path, format=output_format.upper(), **save_kwargs)
                
                return True, None
                
        except Exception as e:
            return False, str(e)
    
    def _save_as_dds(self, img, output_path, dds_format):
        """DDS 포맷으로 저장"""
        try:
            # DDS 저장을 위해 OpenCV 사용 (더 안정적)
            if img.mode == 'RGBA':
                # PIL RGB -> OpenCV BGR 변환
                img_array = np.array(img)
                # RGBA -> BGRA 변환
                img_bgra = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGRA)
            else:
                img_array = np.array(img.convert('RGB'))
                # RGB -> BGR 변환
                img_bgra = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            
            # OpenCV로 저장 (기본 DDS 저장)
            # 주의: OpenCV의 DDS 지원은 제한적이므로 기본 포맷 사용
            success = cv2.imwrite(output_path, img_bgra)
            if not success:
                # OpenCV 실패 시 PIL로 대체 (PNG로 저장 후 확장자만 변경)
                temp_path = output_path.replace('.dds', '.png')
                img.save(temp_path, 'PNG')
                # 파일 이름 변경
                import shutil
                shutil.move(temp_path, output_path)
            
        except Exception as e:
            # 마지막 대안: PIL로 저장
            img.save(output_path, 'PNG')
    
    def batch_convert(self, file_list, output_dir, output_format='PNG', dds_format='RGBA', quality=95):
        """일괄 변환"""
        results = []
        
        for input_file in file_list:
            try:
                input_path = Path(input_file)
                
                # 출력 파일명 생성
                output_filename = input_path.stem + '.' + output_format.lower()
                output_path = Path(output_dir) / output_filename
                
                # 변환 실행
                success, error = self.convert_image(
                    str(input_path), str(output_path), output_format, dds_format, quality
                )
                
                results.append({
                    'input': str(input_path),
                    'output': str(output_path),
                    'success': success,
                    'error': error
                })
                
            except Exception as e:
                results.append({
                    'input': str(input_file),
                    'output': '',
                    'success': False,
                    'error': str(e)
                })
        
        return results


class BatchConvertDialog(QDialog):
    """GFX 일괄 변환 대화상자"""
    
    def __init__(self, parent=None, mod_folder_path=None):
        super().__init__(parent)
        self.setWindowTitle("GFX 일괄 변환 도구")
        self.setModal(True)
        self.resize(700, 500)
        self.mod_folder_path = mod_folder_path
        self.converter = ImageConverter()
        self.selected_files = []
        
        self.init_ui()
    
    def init_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 설명
        desc_label = QLabel("""
이미지 파일을 다른 포맷으로 일괄 변환합니다.
DDS 변환 시 HOI4에 최적화된 포맷을 사용합니다.
        """)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # 파일 선택 영역
        file_group = QGroupBox("변환할 파일 선택")
        file_layout = QVBoxLayout()
        file_group.setLayout(file_layout)
        
        file_btn_layout = QHBoxLayout()
        self.add_files_btn = QPushButton("파일 추가")
        self.add_files_btn.clicked.connect(self.add_files)
        
        self.add_folder_btn = QPushButton("폴더 추가")
        self.add_folder_btn.clicked.connect(self.add_folder)
        
        self.clear_btn = QPushButton("목록 지우기")
        self.clear_btn.clicked.connect(self.clear_files)
        
        file_btn_layout.addWidget(self.add_files_btn)
        file_btn_layout.addWidget(self.add_folder_btn)
        file_btn_layout.addWidget(self.clear_btn)
        file_btn_layout.addStretch()
        
        file_layout.addLayout(file_btn_layout)
        
        # 파일 목록
        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(150)
        file_layout.addWidget(self.file_list)
        
        layout.addWidget(file_group)
        
        # 변환 설정
        settings_group = QGroupBox("변환 설정")
        settings_layout = QFormLayout()
        settings_group.setLayout(settings_layout)
        
        # 출력 폴더
        self.output_dir_edit = QLineEdit()
        output_btn = QPushButton("찾아보기")
        output_btn.clicked.connect(self.browse_output_dir)
        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_dir_edit)
        output_layout.addWidget(output_btn)
        settings_layout.addRow("출력 폴더:", output_layout)
        
        # 출력 포맷
        self.format_combo = QComboBox()
        self.format_combo.addItems(['PNG', 'JPG', 'DDS', 'BMP'])
        self.format_combo.setCurrentText('DDS')  # DDS를 기본값으로
        self.format_combo.currentTextChanged.connect(self.on_format_changed)
        settings_layout.addRow("출력 포맷:", self.format_combo)
        
        # DDS 포맷 설정 (DDS 선택 시만 표시)
        self.dds_format_combo = QComboBox()
        for format_name in ImageConverter.DDS_FORMATS.keys():
            self.dds_format_combo.addItem(format_name)
        self.dds_format_combo.setCurrentText('B8G8R8A8 (Linear, A8R8G8B8)')  # 기본값
        settings_layout.addRow("DDS 포맷:", self.dds_format_combo)
        
        # 품질 설정 (JPG용)
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(95)
        self.quality_spin.setSuffix('%')
        settings_layout.addRow("JPG 품질:", self.quality_spin)
        
        layout.addWidget(settings_group)
        
        # 진행률
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 결과 영역
        self.result_text = QTextEdit()
        self.result_text.setMaximumHeight(100)
        self.result_text.setVisible(False)
        layout.addWidget(self.result_text)
        
        # 버튼
        button_layout = QHBoxLayout()
        
        self.convert_btn = QPushButton("변환 시작")
        self.convert_btn.clicked.connect(self.start_conversion)
        
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.close)
        
        button_layout.addWidget(self.convert_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # 초기 상태 설정
        self.on_format_changed('DDS')
        
        # 기본 출력 폴더 설정
        if self.mod_folder_path:
            self.output_dir_edit.setText(os.path.join(self.mod_folder_path, "gfx", "interface"))
    
    def on_format_changed(self, format_name):
        """출력 포맷 변경 시 UI 업데이트"""
        # DDS 포맷 설정은 DDS 선택 시만 표시
        self.dds_format_combo.setVisible(format_name == 'DDS')
        
        # JPG 품질 설정은 JPG 선택 시만 표시
        self.quality_spin.setVisible(format_name == 'JPG')
    
    def add_files(self):
        """파일 추가"""
        default_path = self.mod_folder_path if self.mod_folder_path else os.path.expanduser("~/Documents")
        
        files, _ = QFileDialog.getOpenFileNames(
            self, "변환할 이미지 파일 선택", default_path,
            "이미지 파일 (*.png *.jpg *.jpeg *.bmp *.tiff *.tga);;모든 파일 (*)"
        )
        
        for file in files:
            if file not in self.selected_files:
                self.selected_files.append(file)
                self.file_list.addItem(os.path.basename(file))
    
    def add_folder(self):
        """폴더의 모든 이미지 파일 추가"""
        default_path = self.mod_folder_path if self.mod_folder_path else os.path.expanduser("~/Documents")
        
        folder = QFileDialog.getExistingDirectory(self, "이미지 폴더 선택", default_path)
        if folder:
            extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tga']
            for ext in extensions:
                for file_path in Path(folder).rglob(f"*{ext}"):
                    file_str = str(file_path)
                    if file_str not in self.selected_files:
                        self.selected_files.append(file_str)
                        self.file_list.addItem(os.path.relpath(file_str, folder))
    
    def clear_files(self):
        """파일 목록 지우기"""
        self.selected_files.clear()
        self.file_list.clear()
    
    def browse_output_dir(self):
        """출력 폴더 선택"""
        default_path = self.mod_folder_path if self.mod_folder_path else os.path.expanduser("~/Documents")
        
        folder = QFileDialog.getExistingDirectory(self, "출력 폴더 선택", default_path)
        if folder:
            self.output_dir_edit.setText(folder)
    
    def start_conversion(self):
        """변환 시작"""
        if not self.selected_files:
            QMessageBox.warning(self, "경고", "변환할 파일을 선택해주세요.")
            return
        
        output_dir = self.output_dir_edit.text().strip()
        if not output_dir:
            QMessageBox.warning(self, "경고", "출력 폴더를 선택해주세요.")
            return
        
        # 출력 폴더 생성
        os.makedirs(output_dir, exist_ok=True)
        
        # 변환 설정
        output_format = self.format_combo.currentText()
        dds_format = ImageConverter.DDS_FORMATS[self.dds_format_combo.currentText()]
        quality = self.quality_spin.value()
        
        # 진행률 표시
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.selected_files))
        self.progress_bar.setValue(0)
        self.result_text.setVisible(True)
        self.result_text.clear()
        
        self.convert_btn.setEnabled(False)
        
        # 변환 실행
        results = self.converter.batch_convert(
            self.selected_files, output_dir, output_format, dds_format, quality
        )
        
        # 결과 처리
        success_count = 0
        error_count = 0
        result_text = f"=== 변환 결과 ===\n\n"
        
        for i, result in enumerate(results):
            self.progress_bar.setValue(i + 1)
            QApplication.processEvents()
            
            if result['success']:
                success_count += 1
                result_text += f"✓ {os.path.basename(result['input'])} → {os.path.basename(result['output'])}\n"
            else:
                error_count += 1
                result_text += f"✗ {os.path.basename(result['input'])}: {result['error']}\n"
        
        result_text += f"\n성공: {success_count}개, 실패: {error_count}개"
        self.result_text.setText(result_text)
        
        self.convert_btn.setEnabled(True)
        
        if error_count == 0:
            QMessageBox.information(self, "완료", f"모든 파일이 성공적으로 변환되었습니다.\n변환된 파일: {success_count}개")
        else:
            QMessageBox.warning(self, "변환 완료", f"변환이 완료되었습니다.\n성공: {success_count}개, 실패: {error_count}개")


class FocusGFXShineGenerator:
    """Focus GFX Shine 효과 생성기"""
    
    def __init__(self):
        self.goal_regex = re.compile(
            r'name\s*=\s*"([^"]+)?"(?:[^}]*?)texturefile\s*=\s*"([^"]+)?"', 
            re.MULTILINE | re.DOTALL | re.IGNORECASE
        )
        self.goal_name_regex = re.compile(
            r'name\s*=\s*"([^"]+)?"', 
            re.MULTILINE | re.DOTALL | re.IGNORECASE
        )
        self.comments_regex = re.compile(r'#.*$', re.MULTILINE)
    
    def get_shine_definition(self, name, path):
        """Shine 정의 생성"""
        # 모드 폴더 기준 상대 경로로 변환
        rel_path = path.replace('\\', '/')
        
        return f'''\tSpriteType = {{
\t\tname = "{name}_shine"
\t\ttexturefile = "{rel_path}"
\t\teffectFile = "gfx/FX/buttonstate.lua"
\t\tanimation = {{
\t\t\tanimationmaskfile = "{rel_path}"
\t\t\tanimationtexturefile = "gfx/interface/goals/shine_overlay.dds"
\t\t\tanimationrotation = -90.0
\t\t\tanimationlooping = no
\t\t\tanimationtime = 0.75
\t\t\tanimationdelay = 0
\t\t\tanimationblendmode = "add"
\t\t\tanimationtype = "scrolling"
\t\t\tanimationrotationoffset = {{ x = 0.0 y = 0.0 }}
\t\t\tanimationtexturescale = {{ x = 1.0 y = 1.0 }}
\t\t}}

\t\tanimation = {{
\t\t\tanimationmaskfile = "{rel_path}"
\t\t\tanimationtexturefile = "gfx/interface/goals/shine_overlay.dds"
\t\t\tanimationrotation = 90.0
\t\t\tanimationlooping = no
\t\t\tanimationtime = 0.75
\t\t\tanimationdelay = 0
\t\t\tanimationblendmode = "add"
\t\t\tanimationtype = "scrolling"
\t\t\tanimationrotationoffset = {{ x = 0.0 y = 0.0 }}
\t\t\tanimationtexturescale = {{ x = 1.0 y = 1.0 }}
\t\t}}
\t\tlegacy_lazy_load = no
\t}}'''
    
    def process_files(self, goals_file, goals_shine_file):
        """Focus GFX와 Shine 파일 처리"""
        try:
            # Goals shine 파일 읽기
            with open(goals_shine_file, 'r', encoding='utf-8') as f:
                goals_shine_content = f.read()
            
            # 기존 shine 항목 찾기
            goals_shine_matches = self.goal_name_regex.findall(
                self.comments_regex.sub('', goals_shine_content)
            )
            goals_shine_set = set(goals_shine_matches)
            
            # 마지막 중괄호 위치 찾기
            last_bracket_idx = 0
            for i in range(len(goals_shine_content) - 1, -1, -1):
                if goals_shine_content[i] == '}':
                    last_bracket_idx = i
                    break
            
            goals_shine_split = [
                goals_shine_content[:last_bracket_idx], 
                goals_shine_content[last_bracket_idx:]
            ]
            
            # Goals 파일 읽기
            with open(goals_file, 'r', encoding='utf-8') as f:
                goals_content = f.read()
            
            # Goals 매치 찾기
            goals_matches = self.goal_regex.findall(
                self.comments_regex.sub('', goals_content)
            )
            
            # 누락된 shine 항목 필터링
            missing_shine = {
                name: path for name, path in goals_matches 
                if f"{name}_shine" not in goals_shine_set
            }
            
            # 새로운 shine 정의 추가
            added_count = 0
            for name, path in missing_shine.items():
                shine_def = self.get_shine_definition(name, path)
                goals_shine_split.insert(1, shine_def)
                added_count += 1
            
            # 파일 저장
            if added_count > 0:
                with open(goals_shine_file, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(goals_shine_split))
            
            return {
                'success': True,
                'added_count': added_count,
                'missing_shine': list(missing_shine.keys())
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


class FocusShineDialog(QDialog):
    """Focus GFX Shine 생성 다이얼로그"""
    def __init__(self, parent=None, mod_folder_path=None):
        super().__init__(parent)
        self.setWindowTitle("Focus GFX Shine 생성기")
        self.setModal(True)
        self.resize(600, 400)
        self.generator = FocusGFXShineGenerator()
        self.mod_folder_path = mod_folder_path
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 설명
        desc_label = QLabel("""
Focus tree의 GFX 파일에서 누락된 shine 효과를 자동으로 생성합니다.
Goals GFX 파일과 Goals Shine GFX 파일을 선택하세요.
        """)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # 파일 선택
        form_layout = QFormLayout()
        
        self.goals_file_edit = QLineEdit()
        goals_browse_btn = QPushButton("찾아보기")
        goals_browse_btn.clicked.connect(self.browse_goals_file)
        goals_layout = QHBoxLayout()
        goals_layout.addWidget(self.goals_file_edit)
        goals_layout.addWidget(goals_browse_btn)
        form_layout.addRow("Goals GFX 파일:", goals_layout)
        
        self.shine_file_edit = QLineEdit()
        shine_browse_btn = QPushButton("찾아보기")
        shine_browse_btn.clicked.connect(self.browse_shine_file)
        shine_layout = QHBoxLayout()
        shine_layout.addWidget(self.shine_file_edit)
        shine_layout.addWidget(shine_browse_btn)
        form_layout.addRow("Goals Shine GFX 파일:", shine_layout)
        
        layout.addLayout(form_layout)
        
        # 결과 표시
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMaximumHeight(150)
        layout.addWidget(QLabel("결과:"))
        layout.addWidget(self.result_text)
        
        # 버튼
        button_layout = QHBoxLayout()
        
        self.generate_btn = QPushButton("Shine 생성")
        self.generate_btn.clicked.connect(self.generate_shine)
        button_layout.addWidget(self.generate_btn)
        
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def browse_goals_file(self):
        """Goals 파일 선택"""
        default_path = self.mod_folder_path if self.mod_folder_path else os.path.expanduser(r"~\Documents\Paradox Interactive\Hearts of Iron IV\mod")
        if not os.path.exists(default_path):
            default_path = os.path.expanduser("~/Documents")
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Goals GFX 파일 선택", default_path, 
            "GFX 파일 (*.gfx);;모든 파일 (*)"
        )
        if file_path:
            if self.mod_folder_path and file_path.startswith(self.mod_folder_path):
                relative_path = os.path.relpath(file_path, self.mod_folder_path)
                self.goals_file_edit.setText(relative_path)
            else:
                self.goals_file_edit.setText(file_path)
    
    def browse_shine_file(self):
        """Shine 파일 선택"""
        default_path = self.mod_folder_path if self.mod_folder_path else os.path.expanduser(r"~\Documents\Paradox Interactive\Hearts of Iron IV\mod")
        if not os.path.exists(default_path):
            default_path = os.path.expanduser("~/Documents")
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Goals Shine GFX 파일 선택", default_path, 
            "GFX 파일 (*.gfx);;모든 파일 (*)"
        )
        if file_path:
            if self.mod_folder_path and file_path.startswith(self.mod_folder_path):
                relative_path = os.path.relpath(file_path, self.mod_folder_path)
                self.shine_file_edit.setText(relative_path)
            else:
                self.shine_file_edit.setText(file_path)
    
    def generate_shine(self):
        """Shine 효과 생성"""
        goals_file = self.goals_file_edit.text().strip()
        shine_file = self.shine_file_edit.text().strip()
        
        if not goals_file or not shine_file:
            QMessageBox.warning(self, "경고", "Goals 파일과 Shine 파일을 모두 선택해주세요.")
            return
        
        # 상대 경로인 경우 절대 경로로 변환
        if self.mod_folder_path and not os.path.isabs(goals_file):
            goals_file = os.path.join(self.mod_folder_path, goals_file)
        if self.mod_folder_path and not os.path.isabs(shine_file):
            shine_file = os.path.join(self.mod_folder_path, shine_file)
        
        if not os.path.exists(goals_file):
            QMessageBox.warning(self, "경고", f"Goals 파일을 찾을 수 없습니다: {goals_file}")
            return
        
        if not os.path.exists(shine_file):
            QMessageBox.warning(self, "경고", f"Shine 파일을 찾을 수 없습니다: {shine_file}")
            return
        
        # 진행 상황 표시
        self.result_text.setText("Shine 효과를 생성 중...")
        self.generate_btn.setEnabled(False)
        QApplication.processEvents()
        
        try:
            result = self.generator.process_files(goals_file, shine_file)
            
            if result['success']:
                if result['added_count'] > 0:
                    message = f"성공적으로 {result['added_count']}개의 shine 효과를 생성했습니다!\n\n"
                    message += "추가된 항목들:\n"
                    for name in result['missing_shine']:
                        message += f"  - {name}_shine\n"
                    self.result_text.setText(message)
                    QMessageBox.information(self, "완료", f"{result['added_count']}개의 shine 효과가 생성되었습니다.")
                else:
                    self.result_text.setText("ℹ️ 추가할 shine 효과가 없습니다. 모든 항목이 이미 존재합니다.")
                    QMessageBox.information(self, "완료", "추가할 shine 효과가 없습니다.")
            else:
                error_msg = f"오류가 발생했습니다: {result['error']}"
                self.result_text.setText(error_msg)
                QMessageBox.critical(self, "오류", result['error'])
                
        except Exception as e:
            error_msg = f"예상치 못한 오류: {str(e)}"
            self.result_text.setText(error_msg)
            QMessageBox.critical(self, "오류", str(e))
        
        finally:
            self.generate_btn.setEnabled(True)


class DragDropDialog(QDialog):
    """드래그 앤 드롭으로 추가할 GFX 설정 다이얼로그"""
    def __init__(self, parent=None, image_file_path=""):
        super().__init__(parent)
        self.setWindowTitle("새 GFX 추가")
        self.setModal(True)
        self.resize(500, 400)
        self.image_file_path = image_file_path
        
        layout = QFormLayout()
        self.setLayout(layout)
        
        # 원본 파일 경로 표시
        self.source_label = QLabel(f"원본 파일: {os.path.basename(image_file_path)}")
        layout.addRow(self.source_label)
        
        # GFX 이름 (자동 생성된 기본값)
        filename = Path(image_file_path).stem
        default_name = f"GFX_{filename}"
        self.name_edit = QLineEdit(default_name)
        layout.addRow("GFX 이름:", self.name_edit)
        
        # 대상 폴더 선택 (모드 내 경로)
        target_layout = QHBoxLayout()
        self.target_edit = QLineEdit("gfx/interface/")
        self.target_browse_btn = QPushButton("찾기...")
        self.target_browse_btn.clicked.connect(self.browse_target_folder)
        target_layout.addWidget(self.target_edit)
        target_layout.addWidget(self.target_browse_btn)
        layout.addRow("저장할 폴더:", target_layout)
        
        # 대상 GFX 파일
        self.gfx_file_combo = QComboBox()
        layout.addRow("저장할 GFX 파일:", self.gfx_file_combo)
        
        # 미리보기 이미지
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMaximumHeight(150)
        self.preview_label.setStyleSheet("border: 1px solid gray;")
        layout.addRow("미리보기:", self.preview_label)
        self.load_preview()
        
        # 버튼
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
    
    def browse_target_folder(self):
        """대상 폴더 선택"""
        # 기본 시작 경로 설정
        default_path = ""
        if hasattr(self.parent(), 'mod_folder_path') and self.parent().mod_folder_path:
            default_path = self.parent().mod_folder_path
        else:
            default_path = os.path.expanduser(r"~\Documents\Paradox Interactive\Hearts of Iron IV\mod")
            if not os.path.exists(default_path):
                default_path = os.path.expanduser("~/Documents")
        
        folder = QFileDialog.getExistingDirectory(self, "저장할 폴더 선택", default_path)
        if folder and hasattr(self.parent(), 'mod_folder_path') and self.parent().mod_folder_path:
            # 모드 폴더 기준 상대 경로로 변환
            try:
                rel_path = os.path.relpath(folder, self.parent().mod_folder_path)
                self.target_edit.setText(rel_path.replace(os.sep, '/') + '/')
            except ValueError:
                # 다른 드라이브인 경우
                self.target_edit.setText(folder.replace(os.sep, '/') + '/')
    
    def load_preview(self):
        """이미지 미리보기 로드"""
        try:
            with Image.open(self.image_file_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                temp_path = "temp_dragdrop_preview.png"
                img.save(temp_path, "PNG")
                
                pixmap = QPixmap(temp_path)
                scaled_pixmap = pixmap.scaled(
                    120, 120, 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                
                self.preview_label.setPixmap(scaled_pixmap)
                
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
        except Exception as e:
            self.preview_label.setText(f"미리보기 로드 실패: {str(e)}")
    
    def get_data(self):
        """입력된 데이터 반환"""
        return {
            'name': self.name_edit.text().strip(),
            'target_folder': self.target_edit.text().strip(),
            'gfx_file': self.gfx_file_combo.currentText(),
            'source_file': self.image_file_path
        }


class GFXEditDialog(QDialog):
    """GFX 편집 다이얼로그"""
    def __init__(self, parent=None, gfx_name="", texture_path="", is_edit=False):
        super().__init__(parent)
        self.setWindowTitle("GFX 편집" if is_edit else "새 GFX 추가")
        self.setModal(True)
        self.resize(500, 300)
        
        layout = QFormLayout()
        self.setLayout(layout)
        
        # GFX 이름
        self.name_edit = QLineEdit(gfx_name)
        layout.addRow("GFX 이름:", self.name_edit)
        
        # 텍스처 파일 경로
        texture_layout = QHBoxLayout()
        self.texture_edit = QLineEdit(texture_path)
        self.browse_btn = QPushButton("찾기...")
        self.browse_btn.clicked.connect(self.browse_texture)
        texture_layout.addWidget(self.texture_edit)
        texture_layout.addWidget(self.browse_btn)
        layout.addRow("텍스처 파일:", texture_layout)
        
        # 대상 GFX 파일
        self.gfx_file_combo = QComboBox()
        layout.addRow("저장할 GFX 파일:", self.gfx_file_combo)
        
        # 버튼
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
    def browse_texture(self):
        """텍스처 파일 선택"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "텍스처 파일 선택", "", 
            "이미지 파일 (*.dds *.png *.jpg *.jpeg *.bmp *.tga);;DDS 파일 (*.dds);;PNG 파일 (*.png);;모든 파일 (*)"
        )
        if file_path:
            self.texture_edit.setText(file_path)
    
    def get_data(self):
        """입력된 데이터 반환"""
        return {
            'name': self.name_edit.text().strip(),
            'texture_path': self.texture_edit.text().strip(),
            'gfx_file': self.gfx_file_combo.currentText()
        }


class BatchImportDialog(QDialog):
    """일괄 임포트 다이얼로그"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("일괄 임포트")
        self.setModal(True)
        self.resize(600, 400)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 소스 폴더 선택
        folder_layout = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_btn = QPushButton("폴더 선택...")
        self.folder_btn.clicked.connect(self.select_folder)
        folder_layout.addWidget(QLabel("소스 폴더:"))
        folder_layout.addWidget(self.folder_edit)
        folder_layout.addWidget(self.folder_btn)
        layout.addLayout(folder_layout)
        
        # 옵션
        options_group = QGroupBox("옵션")
        options_layout = QFormLayout()
        options_group.setLayout(options_layout)
        
        self.prefix_edit = QLineEdit("GFX_")
        options_layout.addRow("GFX 이름 접두사:", self.prefix_edit)
        
        self.target_gfx_combo = QComboBox()
        options_layout.addRow("대상 GFX 파일:", self.target_gfx_combo)
        
        self.recursive_cb = QCheckBox()
        self.recursive_cb.setChecked(True)
        options_layout.addRow("하위 폴더 포함:", self.recursive_cb)
        
        layout.addWidget(options_group)
        
        # 이미지 저장 경로 설정
        path_group = QGroupBox("이미지 파일 저장 경로")
        path_layout = QVBoxLayout()
        path_group.setLayout(path_layout)
        
        # 저장 방식 선택
        save_option_layout = QHBoxLayout()
        self.copy_to_mod_rb = QRadioButton("모드 폴더로 복사")
        self.copy_to_mod_rb.setChecked(True)
        self.use_original_path_rb = QRadioButton("원본 경로 사용")
        save_option_layout.addWidget(self.copy_to_mod_rb)
        save_option_layout.addWidget(self.use_original_path_rb)
        path_layout.addLayout(save_option_layout)
        
        # 복사 대상 폴더 선택
        self.dest_folder_layout = QHBoxLayout()
        self.dest_folder_edit = QLineEdit("gfx/interface")
        self.dest_folder_btn = QPushButton("찾아보기...")
        self.dest_folder_btn.clicked.connect(self.select_dest_folder)
        self.dest_folder_layout.addWidget(QLabel("저장 폴더 (모드 폴더 기준):"))
        self.dest_folder_layout.addWidget(self.dest_folder_edit)
        self.dest_folder_layout.addWidget(self.dest_folder_btn)
        path_layout.addLayout(self.dest_folder_layout)
        
        # 라디오 버튼 이벤트 연결
        self.copy_to_mod_rb.toggled.connect(self.on_save_option_changed)
        self.use_original_path_rb.toggled.connect(self.on_save_option_changed)
        
        layout.addWidget(path_group)
        
        # 미리보기
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        layout.addWidget(QLabel("미리보기:"))
        layout.addWidget(self.preview_text)
        
        # 버튼
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.folder_edit.textChanged.connect(self.update_preview)
        self.prefix_edit.textChanged.connect(self.update_preview)
        self.dest_folder_edit.textChanged.connect(self.update_preview)
        
    def select_folder(self):
        """폴더 선택"""
        # 기본 시작 경로 설정
        default_path = os.path.expanduser(r"~\Documents\Paradox Interactive\Hearts of Iron IV\mod")
        if not os.path.exists(default_path):
            default_path = os.path.expanduser("~/Documents")
        
        folder = QFileDialog.getExistingDirectory(self, "소스 폴더 선택", default_path)
        if folder:
            self.folder_edit.setText(folder)
    
    def select_dest_folder(self):
        """저장 대상 폴더 선택"""
        # 모드 폴더가 설정되어 있다면 기본 경로로 사용
        parent = self.parent()
        if hasattr(parent, 'mod_folder_path') and parent.mod_folder_path:
            default_path = parent.mod_folder_path
        else:
            default_path = os.path.expanduser("~/Documents")
        
        folder = QFileDialog.getExistingDirectory(self, "저장 폴더 선택", default_path)
        if folder:
            # 모드 폴더 기준 상대 경로로 변환
            if hasattr(parent, 'mod_folder_path') and parent.mod_folder_path:
                try:
                    relative_path = os.path.relpath(folder, parent.mod_folder_path)
                    # 상위 폴더로 나가는 경우 절대 경로 사용
                    if relative_path.startswith('..'):
                        self.dest_folder_edit.setText(folder)
                    else:
                        self.dest_folder_edit.setText(relative_path)
                except ValueError:
                    # 다른 드라이브인 경우 절대 경로 사용
                    self.dest_folder_edit.setText(folder)
            else:
                self.dest_folder_edit.setText(folder)
    
    def on_save_option_changed(self):
        """저장 방식 변경 시 호출"""
        is_copy_mode = self.copy_to_mod_rb.isChecked()
        
        # 복사 모드일 때만 저장 폴더 설정 활성화
        for i in range(self.dest_folder_layout.count()):
            widget = self.dest_folder_layout.itemAt(i).widget()
            if widget:
                widget.setEnabled(is_copy_mode)
        
        self.update_preview()
    
    def update_preview(self):
        """미리보기 업데이트"""
        folder = self.folder_edit.text()
        prefix = self.prefix_edit.text()
        
        if not folder or not os.path.exists(folder):
            self.preview_text.clear()
            return
        
        preview_text = "생성될 GFX 항목들:\n\n"
        
        # 지원되는 이미지 형식들
        image_extensions = ['.dds', '.png', '.jpg', '.jpeg', '.bmp', '.tga']
        image_files = []
        
        for ext in image_extensions:
            pattern = f"**/*{ext}" if self.recursive_cb.isChecked() else f"*{ext}"
            image_files.extend(list(Path(folder).glob(pattern)))
        
        for image_file in image_files[:20]:  # 최대 20개만 미리보기
            relative_path = image_file.relative_to(folder)
            gfx_name = f"{prefix}{relative_path.stem}"
            
            # 저장 경로 표시
            if self.copy_to_mod_rb.isChecked():
                dest_path = os.path.join(self.dest_folder_edit.text(), image_file.name).replace('\\', '/')
                preview_text += f"- {gfx_name} → {dest_path}\n"
            else:
                preview_text += f"- {gfx_name} → {relative_path}\n"
        
        if len(image_files) > 20:
            preview_text += f"\n... 및 {len(image_files) - 20}개 더"
        
        self.preview_text.setText(preview_text)
    
    def get_data(self):
        """입력된 데이터 반환"""
        return {
            'folder': self.folder_edit.text(),
            'prefix': self.prefix_edit.text(),
            'target_gfx_file': self.target_gfx_combo.currentText(),
            'recursive': self.recursive_cb.isChecked(),
            'copy_to_mod': self.copy_to_mod_rb.isChecked(),
            'dest_folder': self.dest_folder_edit.text()
        }


class ProjectManagerDialog(QDialog):
    """프로젝트 관리 다이얼로그"""
    def __init__(self, parent=None, projects=None):
        super().__init__(parent)
        self.setWindowTitle("프로젝트 관리")
        self.setModal(True)
        self.resize(500, 400)
        self.projects = projects or {}
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 프로젝트 목록
        self.project_list = QListWidget()
        self.update_project_list()
        layout.addWidget(QLabel("저장된 프로젝트:"))
        layout.addWidget(self.project_list)
        
        # 버튼들
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("현재 프로젝트 저장")
        self.add_btn.clicked.connect(self.add_project)
        self.load_btn = QPushButton("불러오기")
        self.load_btn.clicked.connect(self.load_project)
        self.delete_btn = QPushButton("삭제")
        self.delete_btn.clicked.connect(self.delete_project)
        
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.load_btn)
        btn_layout.addWidget(self.delete_btn)
        layout.addLayout(btn_layout)
        
        # 닫기 버튼
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        self.selected_project = None
        
    def update_project_list(self):
        """프로젝트 목록 업데이트"""
        self.project_list.clear()
        for name, info in self.projects.items():
            item_text = f"{name} ({info.get('path', 'Unknown')})"
            self.project_list.addItem(item_text)
    
    def add_project(self):
        """현재 프로젝트 저장"""
        name, ok = self.get_project_name()
        if ok and name and hasattr(self.parent(), 'mod_folder_path') and self.parent().mod_folder_path:
            self.projects[name] = {
                'path': self.parent().mod_folder_path,
                'saved_at': datetime.now().isoformat()
            }
            self.update_project_list()
    
    def get_project_name(self):
        """프로젝트 이름 입력 다이얼로그"""
        from PyQt6.QtWidgets import QInputDialog
        return QInputDialog.getText(self, "프로젝트 저장", "프로젝트 이름:")
    
    def load_project(self):
        """선택된 프로젝트 불러오기"""
        current_item = self.project_list.currentItem()
        if current_item:
            project_name = current_item.text().split(' (')[0]
            self.selected_project = self.projects.get(project_name)
            self.accept()
    
    def delete_project(self):
        """선택된 프로젝트 삭제"""
        current_item = self.project_list.currentItem()
        if current_item:
            project_name = current_item.text().split(' (')[0]
            reply = QMessageBox.question(self, "삭제 확인", f"프로젝트 '{project_name}'을 삭제하시겠습니까?")
            if reply == QMessageBox.StandardButton.Yes:
                del self.projects[project_name]
                self.update_project_list()


class AnalysisWorker(QThread):
    """분석 작업을 백그라운드에서 실행하는 워커 스레드"""
    progress_updated = pyqtSignal(int)
    analysis_complete = pyqtSignal(dict)
    
    def __init__(self, mod_folder_path, gfx_data):
        super().__init__()
        self.mod_folder_path = mod_folder_path
        self.gfx_data = gfx_data
        
    def run(self):
        """전체 분석 실행"""
        results = {
            'orphaned_gfx': set(),
            'missing_definitions': set(),
            'duplicate_definitions': {},
            'used_gfx': set(),
            'usage_locations': {}  # {gfx_name: [file_paths]}
        }
        
        self.progress_updated.emit(10)
        
        # 중복 정의 검사
        name_to_files = {}
        for name, info in self.gfx_data.items():
            file_source = info['file_source']
            if name not in name_to_files:
                name_to_files[name] = []
            name_to_files[name].append(file_source)
        
        for name, files in name_to_files.items():
            if len(files) > 1:
                results['duplicate_definitions'][name] = files
        
        self.progress_updated.emit(30)
        
        # 코드 파일에서 GFX 사용처 찾기 (더 많은 파일 형식 지원)
        code_files = []
        file_extensions = ['*.txt', '*.gui', '*.mod', '*.pdx', '*.interface', '*.gfx', '*.lua', '*.yml', '*.yaml']
        for ext in file_extensions:
            code_files.extend(list(Path(self.mod_folder_path).rglob(ext)))
        
        total_files = len(code_files)
        for i, code_file in enumerate(code_files):
            try:
                with open(code_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # 주석 제거 (라인별로 처리)
                lines = content.split('\n')
                clean_content = []
                for line in lines:
                    # 주석 제거 (단, 문자열 내부의 # 은 유지)
                    in_string = False
                    quote_char = None
                    clean_line = ""
                    i = 0
                    while i < len(line):
                        char = line[i]
                        if not in_string and char == '#':
                            break  # 주석 시작, 나머지 무시
                        elif char in ['"', "'"] and (i == 0 or line[i-1] != '\\'):
                            if not in_string:
                                in_string = True
                                quote_char = char
                            elif char == quote_char:
                                in_string = False
                                quote_char = None
                        clean_line += char
                        i += 1
                    clean_content.append(clean_line)
                
                content = '\n'.join(clean_content)
                
                # 확장된 GFX 참조 패턴
                gfx_patterns = [
                    # 기본 속성 패턴
                    r'icon\s*=\s*(["\']?)([A-Za-z0-9_]+)\1',
                    r'texture\s*=\s*(["\']?)([A-Za-z0-9_]+)\1',
                    r'spriteType\s*=\s*(["\']?)([A-Za-z0-9_]+)\1',
                    r'texturefile\s*=\s*(["\']?)([A-Za-z0-9_./\\]+)\1',
                    r'sprite\s*=\s*(["\']?)([A-Za-z0-9_]+)\1',
                    r'frame\s*=\s*(["\']?)([A-Za-z0-9_]+)\1',
                    
                    # GUI 요소에서의 참조
                    r'buttonType\s*=\s*\{[^}]*?quadTextureSprite\s*=\s*(["\']?)([A-Za-z0-9_]+)\1',
                    r'iconType\s*=\s*\{[^}]*?spriteType\s*=\s*(["\']?)([A-Za-z0-9_]+)\1',
                    r'instantTextBoxType\s*=\s*\{[^}]*?font\s*=\s*(["\']?)([A-Za-z0-9_]+)\1',
                    
                    # 직접 GFX 참조
                    r'GFX_[A-Za-z0-9_]+',
                    r'"(GFX_[^"]+)"',
                    r"'(GFX_[^']+)'",
                    
                    # 변수를 통한 참조
                    r'@\[?([A-Za-z0-9_]*GFX[A-Za-z0-9_]*)\]?',
                    r'\$([A-Za-z0-9_]*GFX[A-Za-z0-9_]*)\$',
                    
                    # 전처리기 구문
                    r'@sprite\s*=\s*([A-Za-z0-9_]+)',
                    r'@texture\s*=\s*([A-Za-z0-9_]+)',
                    
                    # 효과 및 애니메이션
                    r'effectFile\s*=\s*(["\']?)([A-Za-z0-9_./\\]+)\1',
                    r'animationmaskfile\s*=\s*(["\']?)([A-Za-z0-9_./\\]+)\1',
                    r'animationtexturefile\s*=\s*(["\']?)([A-Za-z0-9_./\\]+)\1',
                    
                    # Lua 스크립트에서의 참조
                    r'GetSprite\s*\(\s*["\']([^"\'")]+)["\']\s*\)',
                    r'SetSprite\s*\(\s*["\']([^"\'")]+)["\']\s*\)',
                    
                    # 새로운 HOI4 문법
                    r'background\s*=\s*(["\']?)([A-Za-z0-9_]+)\1',
                    r'highlight\s*=\s*(["\']?)([A-Za-z0-9_]+)\1',
                    r'glow\s*=\s*(["\']?)([A-Za-z0-9_]+)\1'
                ]
                
                found_gfx = set()
                for pattern in gfx_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE | re.DOTALL)
                    for match in matches:
                        if isinstance(match, tuple):
                            # 그룹이 여러 개인 경우 비어있지 않은 그룹 선택
                            match = next((m for m in match if m), '')
                        
                        if match and (match.startswith('GFX_') or 'GFX' in match):
                            # 경로에서 GFX 이름 추출 (파일 경로인 경우)
                            if '/' in match or '\\' in match:
                                # 경로에서 파일명만 추출
                                filename = os.path.splitext(os.path.basename(match))[0]
                                if filename.startswith('GFX_') or 'GFX' in filename:
                                    match = filename
                                else:
                                    continue
                            
                            # GFX 이름 정규화
                            match = match.strip('"\'')
                            if match and match in self.gfx_data:
                                # GFX가 정의된 파일에서의 자기 참조는 제외
                                gfx_definition_file = self.gfx_data[match]['file_source']
                                if str(code_file) != gfx_definition_file:
                                    found_gfx.add(match)
                                    results['used_gfx'].add(match)
                                    if match not in results['usage_locations']:
                                        results['usage_locations'][match] = []
                                    if str(code_file) not in results['usage_locations'][match]:
                                        results['usage_locations'][match].append(str(code_file))
                
                # 파일별 사용 GFX 로그
                if found_gfx:
                    print(f"Found {len(found_gfx)} GFX references in {code_file.name}: {', '.join(list(found_gfx)[:5])}{'...' if len(found_gfx) > 5 else ''}")
                            
            except Exception as e:
                print(f"코드 파일 {code_file} 읽기 오류: {e}")
                
            if i % 10 == 0:
                progress = 30 + int((i / total_files) * 50)
                self.progress_updated.emit(progress)
        
        self.progress_updated.emit(80)
        
        # 미사용 GFX 찾기 (더 정밀한 검사)
        for gfx_name in self.gfx_data.keys():
            if gfx_name not in results['used_gfx']:
                # 변형된 이름으로도 검사 (예: GFX_test → test)
                base_name = gfx_name.replace('GFX_', '') if gfx_name.startswith('GFX_') else gfx_name
                is_used = False
                
                # 모든 사용처에서 변형된 이름 검사
                for used_gfx in results['used_gfx']:
                    used_base = used_gfx.replace('GFX_', '') if used_gfx.startswith('GFX_') else used_gfx
                    if base_name == used_base or gfx_name in used_gfx or used_gfx in gfx_name:
                        is_used = True
                        # 사용처 정보 복사 (자기 파일 제외)
                        if used_gfx in results['usage_locations']:
                            if gfx_name not in results['usage_locations']:
                                results['usage_locations'][gfx_name] = []
                            # 자기 파일이 아닌 사용처만 복사
                            gfx_definition_file = self.gfx_data[gfx_name]['file_source']
                            for usage_file in results['usage_locations'][used_gfx]:
                                if usage_file != gfx_definition_file:
                                    results['usage_locations'][gfx_name].append(usage_file)
                        break
                
                if not is_used:
                    results['orphaned_gfx'].add(gfx_name)
        
        # 누락된 정의 찾기
        for used_gfx in results['used_gfx']:
            if used_gfx not in self.gfx_data:
                results['missing_definitions'].add(used_gfx)
        
        # 최종 통계 및 로그
        total_gfx = len(self.gfx_data)
        used_gfx = len(results['used_gfx'])
        orphaned_gfx = len(results['orphaned_gfx'])
        
        print(f"\n=== GFX 사용처 분석 완료 ===")
        print(f"전체 GFX: {total_gfx}개")
        print(f"사용된 GFX: {used_gfx}개 (자기 파일 참조 제외)")
        print(f"미사용 GFX: {orphaned_gfx}개")
        print(f"검사된 파일: {len(code_files)}개")
        
        self.progress_updated.emit(100)
        self.analysis_complete.emit(results)


class GFXTreeWidget(QTreeWidget):
    """드래그 앤 드롭을 지원하는 커스텀 트리 위젯"""
    file_dropped = pyqtSignal(str, QTreeWidgetItem)  # (file_path, target_item)
    
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeWidget.DragDropMode.DropOnly)
        
    def dragEnterEvent(self, event):
        """드래그 진입 이벤트"""
        if event.mimeData().hasUrls():
            # 이미지 파일인지 확인
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.dds', '.png', '.jpg', '.jpeg', '.bmp', '.tga')):
                    event.acceptProposedAction()
                    return
        event.ignore()
    
    def dragMoveEvent(self, event):
        """드래그 이동 이벤트"""
        if event.mimeData().hasUrls():
            # 드롭할 수 있는 항목 위에 있는지 확인
            item = self.itemAt(event.position().toPoint())
            if item:
                # 파일 노드나 GFX 노드 모두 허용
                event.acceptProposedAction()
                self.setCurrentItem(item)  # 현재 항목 강조
            else:
                event.ignore()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        """드롭 이벤트"""
        if event.mimeData().hasUrls():
            item = self.itemAt(event.position().toPoint())
            if item:
                # 이미지 파일만 처리
                for url in event.mimeData().urls():
                    file_path = url.toLocalFile()
                    if file_path.lower().endswith(('.dds', '.png', '.jpg', '.jpeg', '.bmp', '.tga')):
                        self.file_dropped.emit(file_path, item)
                        break
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()


class GFXManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.mod_folder_path = None
        self.gfx_data = {}
        self.orphaned_gfx = set()
        self.missing_definitions = set()
        self.duplicate_definitions = {}
        self.used_gfx = set()
        self.usage_locations = {}
        self.analysis_worker = None
        
        # 설정 및 프로젝트 관리
        self.settings = QSettings('HOI4GFXManager', 'Settings')
        self.projects = self.load_projects()
        self.dark_mode = self.settings.value('dark_mode', False, type=bool)
        
        # 드래그 앤 드롭 활성화
        self.setAcceptDrops(True)
        
        self.init_ui()
        self.apply_theme()
        
        # 상태바 타이머
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)
    
    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle("HOI4 GFX 통합 관리 도구")
        self.setGeometry(100, 100, 1400, 900)
        
        # 메뉴바 설정
        self.create_menus()
        
        # 툴바 설정
        self.create_toolbar()
        
        # 중앙 위젯 설정
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 메인 레이아웃
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # 상단 컨트롤 패널
        control_panel = QHBoxLayout()
        main_layout.addLayout(control_panel)
        
        # 검색 필드
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("GFX 이름 검색...")
        self.search_field.setMaximumWidth(300)  # 너비 제한
        self.search_field.textChanged.connect(self.filter_gfx_list)
        control_panel.addWidget(self.search_field)
        control_panel.addStretch()  # 나머지 공간 채우기
        
        # 탭 위젯
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)
        
        # 메인 탭
        main_tab = QWidget()
        tab_widget.addTab(main_tab, "GFX 목록")
        self.setup_main_tab(main_tab)
        
        # 분석 결과 탭
        analysis_tab = QWidget()
        tab_widget.addTab(analysis_tab, "분석 결과")
        self.setup_analysis_tab(analysis_tab)
        
        # 프로젝트 관리 탭
        project_tab = QWidget()
        tab_widget.addTab(project_tab, "프로젝트")
        self.setup_project_tab(project_tab)
        
        # GUI 프리뷰 탭
        self.gui_preview_widget = GUIPreviewWidget(mod_folder_path=self.mod_folder_path)
        tab_widget.addTab(self.gui_preview_widget, "GUI 프리뷰")
        
        # 진행률 표시
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # 상태바
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("준비")
    
    def create_menus(self):
        """메뉴바 생성"""
        menubar = self.menuBar()
        
        # 파일 메뉴
        file_menu = menubar.addMenu('파일')
        
        open_action = QAction('모드 폴더 열기', self)
        open_action.triggered.connect(self.open_mod_folder)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        export_action = QAction('분석 결과 내보내기', self)
        export_action.triggered.connect(self.export_analysis)
        file_menu.addAction(export_action)
        
        # 편집 메뉴
        edit_menu = menubar.addMenu('편집')
        
        add_gfx_action = QAction('새 GFX 추가', self)
        add_gfx_action.triggered.connect(self.add_gfx)
        edit_menu.addAction(add_gfx_action)
        
        batch_import_action = QAction('일괄 임포트', self)
        batch_import_action.triggered.connect(self.batch_import)
        edit_menu.addAction(batch_import_action)
        
        # 도구 메뉴
        tools_menu = menubar.addMenu('도구')
        
        analyze_action = QAction('전체 분석 실행', self)
        analyze_action.triggered.connect(self.run_full_analysis)
        tools_menu.addAction(analyze_action)
        
        tools_menu.addSeparator()
        
        focus_shine_action = QAction('Focus GFX Shine 생성', self)
        focus_shine_action.triggered.connect(self.open_focus_shine_generator)
        tools_menu.addAction(focus_shine_action)
        
        batch_convert_action = QAction('GFX 일괄 변환', self)
        batch_convert_action.triggered.connect(self.open_batch_converter)
        tools_menu.addAction(batch_convert_action)
        
        # 보기 메뉴
        view_menu = menubar.addMenu('보기')
        
        theme_action = QAction('다크 모드 전환', self)
        theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(theme_action)
    
    def create_toolbar(self):
        """툴바 생성"""
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        # 기본 작업들
        toolbar.addAction("폴더 열기", self.open_mod_folder)
        toolbar.addAction("분석 실행", self.run_full_analysis)
        toolbar.addSeparator()
        toolbar.addAction("GFX 추가", self.add_gfx)
        toolbar.addAction("일괄 임포트", self.batch_import)
        toolbar.addSeparator()
        toolbar.addAction("프로젝트 관리", self.manage_projects)
    
    def setup_main_tab(self, tab):
        """메인 탭 설정"""
        layout = QVBoxLayout()
        tab.setLayout(layout)
        
        # 필터 체크박스들
        filter_group = QGroupBox("필터 옵션")
        filter_group.setMaximumHeight(60)  # 높이 제한
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(5, 5, 5, 5)  # 여백 줄이기
        filter_group.setLayout(filter_layout)
        
        self.show_valid_cb = QCheckBox("정상")
        self.show_valid_cb.setChecked(True)
        self.show_valid_cb.toggled.connect(self.filter_gfx_list)
        filter_layout.addWidget(self.show_valid_cb)
        
        self.show_missing_cb = QCheckBox("파일 없음")
        self.show_missing_cb.setChecked(True)
        self.show_missing_cb.toggled.connect(self.filter_gfx_list)
        filter_layout.addWidget(self.show_missing_cb)
        
        self.show_orphaned_cb = QCheckBox("미사용")
        self.show_orphaned_cb.setChecked(True)
        self.show_orphaned_cb.toggled.connect(self.filter_gfx_list)
        filter_layout.addWidget(self.show_orphaned_cb)
        
        self.show_duplicate_cb = QCheckBox("중복")
        self.show_duplicate_cb.setChecked(True)
        self.show_duplicate_cb.toggled.connect(self.filter_gfx_list)
        filter_layout.addWidget(self.show_duplicate_cb)
        
        filter_layout.addStretch()  # 나머지 공간 채우기
        
        layout.addWidget(filter_group)
        
        # 수평 분할기
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # 좌측: GFX 리스트와 컨트롤
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)
        
        # GFX 트리 (드래그 앤 드롭 지원)
        self.gfx_tree = GFXTreeWidget()
        self.gfx_tree.setHeaderLabels(["Name", "Status", "File", "Type"])
        self.gfx_tree.itemClicked.connect(self.on_gfx_selected)
        self.gfx_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.gfx_tree.customContextMenuRequested.connect(self.show_context_menu)
        # 트리에 드롭 처리 핸들러 연결
        self.gfx_tree.file_dropped.connect(self.handle_tree_drop)
        # 사용법 툴팁 추가
        self.gfx_tree.setToolTip(
            "이미지 파일을 드래그하여 GFX를 관리하세요:\n"
            "• 파일 노드에 드롭: 자동으로 새 GFX 추가\n"
            "• GFX 노드에 드롭: 기존 GFX 텍스처 교체\n"
            "• Ctrl+드롭: 수동으로 설정하여 추가"
        )
        left_layout.addWidget(self.gfx_tree)
        
        # 하단 버튼들
        btn_layout = QHBoxLayout()
        self.edit_gfx_btn = QPushButton("편집")
        self.edit_gfx_btn.clicked.connect(self.edit_selected_gfx)
        self.edit_gfx_btn.setEnabled(False)
        
        self.delete_gfx_btn = QPushButton("삭제")
        self.delete_gfx_btn.clicked.connect(self.delete_selected_gfx)
        self.delete_gfx_btn.setEnabled(False)
        
        btn_layout.addWidget(self.edit_gfx_btn)
        btn_layout.addWidget(self.delete_gfx_btn)
        left_layout.addLayout(btn_layout)
        
        splitter.addWidget(left_widget)
        
        # 우측: 이미지 미리보기와 정보
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_widget.setLayout(right_layout)
        
        # 이미지 미리보기
        self.image_label = QLabel("GFX를 선택하면 이미지가 표시됩니다")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                border: 2px dashed #ccc;
                border-radius: 8px;
                padding: 20px;
                color: #666;
                font-size: 14px;
                background-color: #f9f9f9;
            }
        """)
        self.image_label.setMinimumSize(400, 300)
        right_layout.addWidget(self.image_label)
        
        # GFX 정보
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(150)
        right_layout.addWidget(self.info_text)
        
        splitter.addWidget(right_widget)
        splitter.setSizes([400, 800])
    
    def setup_analysis_tab(self, tab):
        """분석 결과 탭 설정"""
        layout = QVBoxLayout()
        tab.setLayout(layout)
        
        # 상단 통계 요약
        stats_group = QGroupBox("분석 통계")
        stats_layout = QHBoxLayout()
        stats_group.setLayout(stats_layout)
        
        # 통계 레이블들
        self.total_gfx_label = QLabel("총 GFX: 0개")
        self.valid_gfx_label = QLabel("정상: 0개")
        self.error_gfx_label = QLabel("오류: 0개")
        self.orphaned_gfx_label = QLabel("미사용: 0개")
        
        stats_layout.addWidget(self.total_gfx_label)
        stats_layout.addWidget(QLabel("|"))
        stats_layout.addWidget(self.valid_gfx_label)
        stats_layout.addWidget(QLabel("|"))
        stats_layout.addWidget(self.error_gfx_label)
        stats_layout.addWidget(QLabel("|"))
        stats_layout.addWidget(self.orphaned_gfx_label)
        stats_layout.addStretch()
        
        layout.addWidget(stats_group)
        
        # 분석 결과 텍스트
        self.analysis_text = QTextEdit()
        self.analysis_text.setReadOnly(True)
        layout.addWidget(self.analysis_text)
    
    
    def setup_project_tab(self, tab):
        """프로젝트 탭 설정"""
        layout = QVBoxLayout()
        tab.setLayout(layout)
        
        # 프로젝트 목록
        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderLabels(["프로젝트", "경로", "저장 시간"])
        layout.addWidget(self.project_tree)
        
        # 버튼들
        btn_layout = QHBoxLayout()
        save_project_btn = QPushButton("현재 프로젝트 저장")
        save_project_btn.clicked.connect(self.save_current_project)
        btn_layout.addWidget(save_project_btn)
        
        layout.addLayout(btn_layout)
        
        self.update_project_tree()
    
    def show_context_menu(self, position):
        """컨텍스트 메뉴 표시"""
        item = self.gfx_tree.itemAt(position)
        if item and item.parent():  # Only show menu for child items (GFX items)
            menu = QMenu()
            
            edit_action = menu.addAction("편집")
            edit_action.triggered.connect(self.edit_selected_gfx)
            
            delete_action = menu.addAction("삭제")
            delete_action.triggered.connect(self.delete_selected_gfx)
            
            menu.addSeparator()
            
            open_file_action = menu.addAction("GFX 파일 열기")
            open_file_action.triggered.connect(self.open_gfx_file)
            
            open_texture_action = menu.addAction("텍스처 폴더 열기")
            open_texture_action.triggered.connect(self.open_texture_folder)
            
            menu.exec(self.gfx_tree.mapToGlobal(position))
    
    def apply_theme(self):
        """테마 적용"""
        if self.dark_mode:
            # 다크 모드 (기존 스타일 유지)
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QWidget {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QListWidget, QTextEdit, QLineEdit {
                    background-color: #3c3c3c;
                    border: 1px solid #555555;
                    color: #ffffff;
                }
                QPushButton {
                    background-color: #404040;
                    border: 1px solid #555555;
                    padding: 5px;
                    color: #ffffff;
                }
                QPushButton:hover {
                    background-color: #505050;
                }
                QMenuBar {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QMenuBar::item:selected {
                    background-color: #404040;
                }
            """)
        else:
            # 라이트 모드 - 기본 스타일
            self.setStyleSheet("")
    
    def toggle_theme(self):
        """테마 전환"""
        self.dark_mode = not self.dark_mode
        self.settings.setValue('dark_mode', self.dark_mode)
        self.apply_theme()
    
    def open_mod_folder(self):
        """모드 폴더 선택"""
        # HOI4 기본 모드 경로 설정
        default_path = os.path.expanduser(r"~\Documents\Paradox Interactive\Hearts of Iron IV\mod")
        
        # 경로가 존재하지 않으면 Documents 폴더로 대체
        if not os.path.exists(default_path):
            default_path = os.path.expanduser("~/Documents")
        
        folder_path = QFileDialog.getExistingDirectory(self, "HOI4 모드 폴더 선택", default_path)
        if folder_path:
            self.mod_folder_path = folder_path
            # GUI 프리뷰어에도 모드 폴더 경로 업데이트
            if hasattr(self, 'gui_preview_widget'):
                self.gui_preview_widget.mod_folder_path = self.mod_folder_path
            self.scan_gfx_files()
    
    def scan_gfx_files(self):
        """GFX 파일 스캔"""
        if not self.mod_folder_path:
            return
        
        self.gfx_data.clear()
        self.gfx_tree.clear()
        
        try:
            gfx_files = list(Path(self.mod_folder_path).rglob("*.gfx"))
            
            if not gfx_files:
                QMessageBox.information(self, "알림", "선택한 폴더에서 .gfx 파일을 찾을 수 없습니다.")
                return
            
            for gfx_file in gfx_files:
                self.parse_gfx_file(gfx_file)
            
            self.update_gfx_list()
            self.update_gui_preview_data()
            self.update_statistics_cards()  # 통계 카드 업데이트
            self.status_bar.showMessage(f"{len(gfx_files)}개의 .gfx 파일에서 {len(self.gfx_data)}개의 GFX를 찾았습니다.")
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"GFX 파일 스캔 중 오류: {str(e)}")
    
    def parse_gfx_file(self, gfx_file_path):
        """GFX 파일 파싱"""
        try:
            with open(gfx_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # 주석 제거
            lines = content.split('\n')
            cleaned_lines = []
            for line in lines:
                if '#' in line:
                    line = line[:line.index('#')]
                cleaned_lines.append(line)
            
            content = '\n'.join(cleaned_lines)
            
            # spriteType 블록 찾기 (대소문자 구분 없음)
            sprite_pattern = r'spriteType\s*=\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}'
            sprite_matches = re.findall(sprite_pattern, content, re.DOTALL | re.IGNORECASE)
            
            for sprite_content in sprite_matches:
                name_match = re.search(r'name\s*=\s*["\']?([^"\'}\s]+)["\']?', sprite_content, re.IGNORECASE)
                texture_match = re.search(r'texturefile\s*=\s*["\']?([^"\'}\s]+)["\']?', sprite_content, re.IGNORECASE)
                
                if name_match and texture_match:
                    name = name_match.group(1).strip('"\'')
                    texture_path = texture_match.group(1).strip('"\'')
                    
                    full_texture_path = os.path.join(self.mod_folder_path, texture_path)
                    status = 'valid' if os.path.exists(full_texture_path) else 'missing_file'
                    
                    if name in self.gfx_data:
                        status = 'duplicate'
                        if name in self.duplicate_definitions:
                            self.duplicate_definitions[name].append(str(gfx_file_path))
                        else:
                            self.duplicate_definitions[name] = [self.gfx_data[name]['file_source'], str(gfx_file_path)]
                    
                    self.gfx_data[name] = {
                        'texturefile': full_texture_path,
                        'file_source': str(gfx_file_path),
                        'status': status,
                        'relative_path': texture_path
                    }
                    
        except Exception as e:
            print(f"파일 {gfx_file_path} 파싱 중 오류: {str(e)}")
    
    def update_gfx_list(self):
        """GFX 트리 업데이트"""
        self.gfx_tree.clear()
        search_text = self.search_field.text().lower()
        
        # 파일별로 그룹화
        file_groups = {}
        for name, info in self.gfx_data.items():
            if search_text and search_text not in name.lower():
                continue
            
            status = info['status']
            
            # 필터 적용
            if status == 'valid' and not self.show_valid_cb.isChecked():
                continue
            elif status == 'missing_file' and not self.show_missing_cb.isChecked():
                continue
            elif status == 'duplicate' and not self.show_duplicate_cb.isChecked():
                continue
            elif name in self.orphaned_gfx and not self.show_orphaned_cb.isChecked():
                continue
            
            file_source = os.path.basename(info['file_source'])
            if file_source not in file_groups:
                file_groups[file_source] = []
            file_groups[file_source].append((name, info))
        
        # 파일별 트리 노드 생성
        for file_source in sorted(file_groups.keys()):
            # 파일 타입 결정
            file_type = "FILE"
            if "interface" in file_source.lower():
                file_type = "INTERFACE"
            elif "common" in file_source.lower():
                file_type = "COMMON"
            elif "events" in file_source.lower():
                file_type = "EVENTS"
            elif "decisions" in file_source.lower():
                file_type = "DECISIONS"
            
            # 파일 노드 생성
            file_item = QTreeWidgetItem([file_source, "", "", file_type])
            file_item.setExpanded(True)
            
            # GFX 항목들 추가
            for name, info in sorted(file_groups[file_source]):
                status = info['status']
                
                # 상태 표시
                status_text = ""
                if status == 'missing_file':
                    status_text = "ERROR"
                elif status == 'duplicate':
                    status_text = "DUPLICATE"
                elif name in self.orphaned_gfx:
                    status_text = "UNUSED"
                else:
                    status_text = "OK"
                
                gfx_item = QTreeWidgetItem([name, status_text, info['relative_path'], "GFX"])
                
                # 색상 설정
                if status == 'missing_file':
                    gfx_item.setBackground(0, QColor(255, 200, 200))
                    gfx_item.setBackground(1, QColor(255, 200, 200))
                elif status == 'duplicate':
                    gfx_item.setBackground(0, QColor(255, 255, 200))
                    gfx_item.setBackground(1, QColor(255, 255, 200))
                elif name in self.orphaned_gfx:
                    gfx_item.setBackground(0, QColor(200, 200, 255))
                    gfx_item.setBackground(1, QColor(200, 200, 255))
                
                file_item.addChild(gfx_item)
            
            self.gfx_tree.addTopLevelItem(file_item)
        
        # 모든 노드 확장
        self.gfx_tree.expandAll()
        
        # 컬럼 크기 조정
        self.gfx_tree.resizeColumnToContents(0)
        self.gfx_tree.resizeColumnToContents(1)
        self.gfx_tree.resizeColumnToContents(2)
        self.gfx_tree.resizeColumnToContents(3)
    
    def filter_gfx_list(self):
        """트리 필터링"""
        self.update_gfx_list()
    
    def on_gfx_selected(self, item, column=0):
        """GFX 선택 시"""
        # 파일 노드가 아닌 GFX 아이템인지 확인
        if not item.parent():
            self.edit_gfx_btn.setEnabled(False)
            self.delete_gfx_btn.setEnabled(False)
            self.image_label.setText("GFX 항목을 선택해주세요")
            self.info_text.clear()
            return
        
        gfx_name = item.text(0)  # 첫 번째 컬럼에서 이름 가져오기
        gfx_info = self.gfx_data.get(gfx_name)
        
        self.edit_gfx_btn.setEnabled(True)
        self.delete_gfx_btn.setEnabled(True)
        
        if not gfx_info:
            self.image_label.setText("이미지 경로를 찾을 수 없습니다")
            self.info_text.clear()
            return
        
        # 정보 표시
        info_text = f"GFX 이름: {gfx_name}\n"
        info_text += f"파일 소스: {gfx_info['file_source']}\n"
        info_text += f"텍스처 경로: {gfx_info['relative_path']}\n"
        info_text += f"상태: {gfx_info['status']}\n"
        
        if gfx_name in self.usage_locations:
            info_text += f"사용처: {len(self.usage_locations[gfx_name])}개 파일\n"
            for location in self.usage_locations[gfx_name][:5]:  # 최대 5개만 표시
                info_text += f"  - {location}\n"
            if len(self.usage_locations[gfx_name]) > 5:
                info_text += f"  ... 및 {len(self.usage_locations[gfx_name]) - 5}개 더\n"
        else:
            info_text += "사용처: 없음 (미사용 GFX)\n"
        
        self.info_text.setText(info_text)
        
        # 이미지 미리보기
        texture_path = gfx_info['texturefile']
        
        if not os.path.exists(texture_path):
            self.image_label.setText(f"이미지 파일이 존재하지 않습니다:\n{texture_path}")
            return
        
        try:
            with Image.open(texture_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                temp_path = "temp_preview.png"
                img.save(temp_path, "PNG")
                
                pixmap = QPixmap(temp_path)
                label_size = self.image_label.size()
                scaled_pixmap = pixmap.scaled(
                    label_size.width() - 10, 
                    label_size.height() - 10, 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                
                self.image_label.setPixmap(scaled_pixmap)
                
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
        except Exception as e:
            self.image_label.setText(f"이미지를 불러올 수 없습니다:\n{str(e)}")
    
    def run_full_analysis(self):
        """전체 분석 실행"""
        if not self.mod_folder_path or not self.gfx_data:
            QMessageBox.warning(self, "경고", "먼저 모드 폴더를 선택하고 GFX 파일을 스캔해주세요.")
            return
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.analysis_worker = AnalysisWorker(self.mod_folder_path, self.gfx_data)
        self.analysis_worker.progress_updated.connect(self.progress_bar.setValue)
        self.analysis_worker.analysis_complete.connect(self.on_analysis_complete)
        self.analysis_worker.start()
    
    def on_analysis_complete(self, results):
        """분석 완료"""
        self.orphaned_gfx = results['orphaned_gfx']
        self.missing_definitions = results['missing_definitions']
        self.duplicate_definitions = results['duplicate_definitions']
        self.used_gfx = results['used_gfx']
        self.usage_locations = results['usage_locations']
        
        # 통계 카드 업데이트
        self.update_statistics_cards()
        
        # 분석 결과 생성
        report = self.generate_analysis_report(results)
        self.analysis_text.setText(report)
        
        self.update_gfx_list()
        self.progress_bar.setVisible(False)
        
        QMessageBox.information(self, "분석 완료", "전체 분석이 완료되었습니다.")
    
    def update_statistics_cards(self):
        """통계 레이블들 업데이트"""
        total_gfx = len(self.gfx_data)
        valid_gfx = len([name for name, info in self.gfx_data.items() if info['status'] == 'valid'])
        error_gfx = len([name for name, info in self.gfx_data.items() if info['status'] in ['missing_file', 'duplicate']])
        orphaned_gfx = len(self.orphaned_gfx) if hasattr(self, 'orphaned_gfx') else 0
        
        self.total_gfx_label.setText(f"총 GFX: {total_gfx}개")
        self.valid_gfx_label.setText(f"정상: {valid_gfx}개")
        self.error_gfx_label.setText(f"오류: {error_gfx}개")
        self.orphaned_gfx_label.setText(f"미사용: {orphaned_gfx}개")
    
    def generate_analysis_report(self, results):
        """더 상세한 분석 리포트 생성"""
        report = "=== HOI4 GFX 사용처 분석 리포트 ===\n\n"
        report += f"분석 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += f"모드 경로: {self.mod_folder_path}\n"
        
        # 검사된 파일 통계
        code_files = []
        file_extensions = ['*.txt', '*.gui', '*.mod', '*.pdx', '*.interface', '*.gfx', '*.lua', '*.yml', '*.yaml']
        for ext in file_extensions:
            code_files.extend(list(Path(self.mod_folder_path).rglob(ext)))
        
        report += f"검사된 파일: {len(code_files)}개\n"
        report += f"검사 파일 형식: {', '.join([ext.replace('*', '') for ext in file_extensions])}\n\n"
        
        # 파일별 통계 추가
        file_stats = {}
        for name, info in self.gfx_data.items():
            file_source = os.path.basename(info['file_source'])
            if file_source not in file_stats:
                file_stats[file_source] = {'total': 0, 'valid': 0, 'error': 0}
            file_stats[file_source]['total'] += 1
            if info['status'] == 'valid':
                file_stats[file_source]['valid'] += 1
            else:
                file_stats[file_source]['error'] += 1
        
        # 상세 통계 계산
        valid_gfx = len([name for name, info in self.gfx_data.items() if info['status'] == 'valid'])
        invalid_gfx = len([name for name, info in self.gfx_data.items() if info['status'] != 'valid'])
        usage_rate = (len(self.used_gfx) / len(self.gfx_data) * 100) if self.gfx_data else 0
        
        report += f"=== 전체 통계 ===\n"
        report += f"┌────────────────────────────────────────┐\n"
        report += f"│ 전체 GFX 정의: {len(self.gfx_data):>15}개 │\n"
        report += f"│  ├─ 정상 GFX: {valid_gfx:>17}개 │\n"
        report += f"│  └─ 오류 GFX: {invalid_gfx:>17}개 │\n"
        report += f"│ 사용 중인 GFX: {len(self.used_gfx):>15}개 │\n"
        report += f"│  (자기 파일 참조 제외)          │\n"
        report += f"│ 미사용 GFX: {len(self.orphaned_gfx):>18}개 │\n"
        report += f"│ 사용률: {usage_rate:>23.1f}% │\n"
        report += f"│                                      │\n"
        report += f"│ 누락된 정의: {len(self.missing_definitions):>17}개 │\n"
        report += f"│ 중복 정의: {len(self.duplicate_definitions):>20}개 │\n"
        report += f"└────────────────────────────────────────┘\n\n"
        
        # 파일별 상세 통계
        if file_stats:
            report += f"=== 파일별 통계 ===\n"
            for file_name, stats in sorted(file_stats.items()):
                icon = "INTERFACE" if "interface" in file_name.lower() else "COMMON" if "common" in file_name.lower() else "FILE"
                report += f"[{icon}] {file_name}:\n"
                report += f"   ├─ 총 개수: {stats['total']}개\n"
                report += f"   ├─ 정상: {stats['valid']}개\n"
                report += f"   └─ 오류: {stats['error']}개\n\n"
        
        # 미사용 GFX 상세 분석
        if self.orphaned_gfx:
            report += f"=== 미사용 GFX 분석 ({len(self.orphaned_gfx)}개) ===\n"
            report += "삭제를 고려할 수 있는 미사용 GFX 목록:\n\n"
            
            # 파일별로 그룹화
            orphaned_by_file = {}
            for gfx in self.orphaned_gfx:
                if gfx in self.gfx_data:
                    file_source = os.path.basename(self.gfx_data[gfx]['file_source'])
                    if file_source not in orphaned_by_file:
                        orphaned_by_file[file_source] = []
                    orphaned_by_file[file_source].append(gfx)
            
            for file_name, gfx_list in sorted(orphaned_by_file.items()):
                report += f"[{file_name}] ({len(gfx_list)}개):\n"
                for gfx in sorted(gfx_list):
                    report += f"  • {gfx}\n"
                report += "\n"
        
        if self.missing_definitions:
            report += "누락된 GFX 정의 (추가 필요):\n"
            for gfx in sorted(self.missing_definitions):
                report += f"  - {gfx}\n"
            report += "\n"
        
        if self.duplicate_definitions:
            report += "중복 정의된 GFX:\n"
            for gfx, files in self.duplicate_definitions.items():
                report += f"  - {gfx}:\n"
                for file in files:
                    report += f"    * {file}\n"
            report += "\n"
        
        # 사용처 상세 분석 (상위 20개)
        if self.usage_locations:
            usage_counts = [(gfx, len(locations)) for gfx, locations in self.usage_locations.items()]
            usage_counts.sort(key=lambda x: x[1], reverse=True)
            
            report += f"=== 많이 사용되는 GFX TOP 20 ===\n"
            for i, (gfx, count) in enumerate(usage_counts[:20], 1):
                report += f"{i:2d}. {gfx} - {count}개 파일에서 사용\n"
            report += "\n"
        
        # 문제 파일 분석
        missing_files = [name for name, info in self.gfx_data.items() if info['status'] == 'missing_file']
        if missing_files:
            report += f"=== 텍스처 파일 누락 ({len(missing_files)}개) ===\n"
            report += "수정이 필요한 GFX 목록:\n\n"
            for gfx in sorted(missing_files):
                report += f"  ✗ {gfx}\n"
                report += f"    경로: {self.gfx_data[gfx]['relative_path']}\n"
                if gfx in self.usage_locations:
                    report += f"    사용처: {len(self.usage_locations[gfx])}개 파일\n"
                report += "\n"
        
        # 최종 추천 사항
        report += "=== 추천 사항 ===\n"
        if self.orphaned_gfx:
            report += f"• {len(self.orphaned_gfx)}개의 미사용 GFX 삭제 검토\n"
        if missing_files:
            report += f"• {len(missing_files)}개의 누락된 텍스처 파일 복구\n"
        if self.duplicate_definitions:
            report += f"• {len(self.duplicate_definitions)}개의 중복 정의 정리\n"
        if not (self.orphaned_gfx or missing_files or self.duplicate_definitions):
            report += "✓ 모든 GFX가 올바르게 설정되어 있습니다!\n"
        
        report += "\n=== 보고서 끝 ===\n"
        return report
    
    def add_gfx(self):
        """새 GFX 추가"""
        if not self.mod_folder_path:
            QMessageBox.warning(self, "경고", "먼저 모드 폴더를 선택해주세요.")
            return
        
        dialog = GFXEditDialog(self)
        gfx_files = list(Path(self.mod_folder_path).rglob("*.gfx"))
        # 모드 폴더 기준 상대 경로로 표시
        relative_paths = [os.path.relpath(str(f), self.mod_folder_path) for f in gfx_files]
        dialog.gfx_file_combo.addItems(relative_paths)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if data['name'] and data['texture_path'] and data['gfx_file']:
                self.save_gfx_to_file(data['name'], data['texture_path'], data['gfx_file'])
                self.scan_gfx_files()  # 다시 스캔
    
    def edit_selected_gfx(self):
        """선택된 GFX 편집"""
        current_item = self.gfx_tree.currentItem()
        if not current_item or not current_item.parent():
            return
        
        gfx_name = current_item.text(0)
        gfx_info = self.gfx_data.get(gfx_name)
        
        if not gfx_info:
            return
        
        dialog = GFXEditDialog(self, gfx_name, gfx_info['relative_path'], True)
        gfx_files = list(Path(self.mod_folder_path).rglob("*.gfx"))
        # 모드 폴더 기준 상대 경로로 표시
        relative_paths = [os.path.relpath(str(f), self.mod_folder_path) for f in gfx_files]
        dialog.gfx_file_combo.addItems(relative_paths)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if data['name'] and data['texture_path'] and data['gfx_file']:
                # 기존 항목 삭제 후 새로 추가
                self.remove_gfx_from_file(gfx_name, gfx_info['file_source'])
                self.save_gfx_to_file(data['name'], data['texture_path'], data['gfx_file'])
                self.scan_gfx_files()
    
    def delete_selected_gfx(self):
        """선택된 GFX 삭제"""
        current_item = self.gfx_tree.currentItem()
        if not current_item or not current_item.parent():
            return
        
        gfx_name = current_item.text(0)
        gfx_info = self.gfx_data.get(gfx_name)
        
        if not gfx_info:
            return
        
        # 사용처 확인
        if gfx_name in self.usage_locations and self.usage_locations[gfx_name]:
            usage_count = len(self.usage_locations[gfx_name])
            reply = QMessageBox.question(
                self, "삭제 확인", 
                f"'{gfx_name}'은(는) {usage_count}개의 파일에서 사용 중입니다.\n정말 삭제하시겠습니까?"
            )
        else:
            reply = QMessageBox.question(
                self, "삭제 확인", 
                f"'{gfx_name}'을(를) 삭제하시겠습니까?"
            )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.remove_gfx_from_file(gfx_name, gfx_info['file_source'])
            self.scan_gfx_files()
    
    def save_gfx_to_file(self, name, texture_path, gfx_file):
        """GFX를 파일에 저장"""
        try:
            # gfx_file이 상대 경로인 경우 절대 경로로 변환
            if not os.path.isabs(gfx_file):
                gfx_file = os.path.join(self.mod_folder_path, gfx_file)
            
            # 모드 폴더 기준 상대 경로로 변환
            if os.path.isabs(texture_path):
                rel_path = os.path.relpath(texture_path, self.mod_folder_path).replace('\\', '/')
            else:
                rel_path = texture_path.replace('\\', '/')
            
            gfx_entry = f'''
\tspriteType = {{
\t\tname = "{name}"
\t\ttexturefile = "{rel_path}"
\t}}'''
            
            with open(gfx_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # spriteTypes 블록 찾아서 추가
            if 'spriteTypes = {' in content:
                # 마지막 } 앞에 추가
                last_brace = content.rfind('}')
                content = content[:last_brace] + gfx_entry + '\n' + content[last_brace:]
            else:
                # spriteTypes 블록이 없으면 새로 생성
                content += f'\n\nspriteTypes = {{{gfx_entry}\n}}\n'
            
            with open(gfx_file, 'w', encoding='utf-8') as f:
                f.write(content)
                
        except Exception as e:
            QMessageBox.critical(self, "오류", f"GFX 저장 중 오류: {str(e)}")
    
    def remove_gfx_from_file(self, name, gfx_file):
        """파일에서 GFX 제거"""
        try:
            with open(gfx_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 해당 spriteType 블록 찾아서 제거
            pattern = rf'spriteType\s*=\s*\{{\s*name\s*=\s*["\']?{re.escape(name)}["\']?[^}}]*\}}'
            content = re.sub(pattern, '', content, flags=re.DOTALL)
            
            with open(gfx_file, 'w', encoding='utf-8') as f:
                f.write(content)
                
        except Exception as e:
            QMessageBox.critical(self, "오류", f"GFX 삭제 중 오류: {str(e)}")
    
    def batch_import(self):
        """일괄 임포트"""
        if not self.mod_folder_path:
            QMessageBox.warning(self, "경고", "먼저 모드 폴더를 선택해주세요.")
            return
        
        dialog = BatchImportDialog(self)
        gfx_files = list(Path(self.mod_folder_path).rglob("*.gfx"))
        # 모드 폴더 기준 상대 경로로 표시
        relative_paths = [os.path.relpath(str(f), self.mod_folder_path) for f in gfx_files]
        dialog.target_gfx_combo.addItems(relative_paths)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            self.perform_batch_import(data)
    
    def perform_batch_import(self, data):
        """일괄 임포트 실행"""
        try:
            folder = Path(data['folder'])
            prefix = data['prefix']
            target_file = data['target_gfx_file']
            recursive = data['recursive']
            copy_to_mod = data.get('copy_to_mod', False)
            dest_folder = data.get('dest_folder', '')
            
            # 지원되는 이미지 형식들
            image_extensions = ['.dds', '.png', '.jpg', '.jpeg', '.bmp', '.tga']
            image_files = []
            
            for ext in image_extensions:
                pattern = f"**/*{ext}" if recursive else f"*{ext}"
                image_files.extend(list(folder.glob(pattern)))
            
            if not image_files:
                QMessageBox.information(self, "알림", "선택한 폴더에서 지원되는 이미지 파일을 찾을 수 없습니다.")
                return
            
            copied_files = 0
            failed_copies = []
            
            for image_file in image_files:
                relative_path = image_file.relative_to(folder)
                gfx_name = f"{prefix}{relative_path.stem}"
                
                # 이미지 파일 경로 처리
                if copy_to_mod and self.mod_folder_path:
                    # 모드 폴더로 복사
                    try:
                        dest_path = Path(self.mod_folder_path) / dest_folder / image_file.name
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # 파일 복사
                        import shutil
                        shutil.copy2(image_file, dest_path)
                        
                        # GFX 파일에는 모드 폴더 기준 상대 경로 저장
                        mod_relative = os.path.relpath(str(dest_path), self.mod_folder_path).replace('\\', '/')
                        copied_files += 1
                        
                    except Exception as e:
                        failed_copies.append(f"{image_file.name}: {str(e)}")
                        # 복사 실패 시 원본 경로 사용
                        full_path = str(image_file)
                        if self.mod_folder_path in full_path:
                            mod_relative = os.path.relpath(full_path, self.mod_folder_path).replace('\\', '/')
                        else:
                            mod_relative = full_path.replace('\\', '/')
                else:
                    # 원본 경로 사용
                    full_path = str(image_file)
                    if self.mod_folder_path in full_path:
                        mod_relative = os.path.relpath(full_path, self.mod_folder_path).replace('\\', '/')
                    else:
                        mod_relative = full_path.replace('\\', '/')
                
                self.save_gfx_to_file(gfx_name, mod_relative, target_file)
            
            self.scan_gfx_files()
            
            # 결과 메시지 표시
            message = f"{len(image_files)}개의 GFX가 추가되었습니다."
            if copy_to_mod:
                message += f"\n복사된 파일: {copied_files}개"
                if failed_copies:
                    message += f"\n복사 실패: {len(failed_copies)}개"
                    if len(failed_copies) <= 5:
                        message += "\n" + "\n".join(failed_copies)
            
            QMessageBox.information(self, "완료", message)
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"일괄 임포트 중 오류: {str(e)}")
    
    def open_focus_shine_generator(self):
        """Focus GFX Shine 생성기 열기"""
        dialog = FocusShineDialog(self, self.mod_folder_path)
        dialog.exec()
    
    def open_batch_converter(self):
        """GFX 일괄 변환 도구 열기"""
        dialog = BatchConvertDialog(self, self.mod_folder_path)
        dialog.exec()
    
    def export_analysis(self):
        """분석 결과 내보내기"""
        if not hasattr(self, 'analysis_text') or not self.analysis_text.toPlainText():
            QMessageBox.warning(self, "경고", "내보낼 분석 결과가 없습니다.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "분석 결과 저장", 
            f"gfx_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "텍스트 파일 (*.txt)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.analysis_text.toPlainText())
                QMessageBox.information(self, "완료", f"분석 결과가 저장되었습니다:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"파일 저장 중 오류: {str(e)}")
    
    def manage_projects(self):
        """프로젝트 관리"""
        dialog = ProjectManagerDialog(self, self.projects)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.selected_project:
                path = dialog.selected_project['path']
                if os.path.exists(path):
                    self.mod_folder_path = path
                    # GUI 프리뷰어에도 모드 폴더 경로 업데이트
                    if hasattr(self, 'gui_preview_widget'):
                        self.gui_preview_widget.mod_folder_path = self.mod_folder_path
                    self.scan_gfx_files()
                else:
                    QMessageBox.warning(self, "경고", "프로젝트 경로가 존재하지 않습니다.")
            
            self.projects = dialog.projects
            self.save_projects()
            self.update_project_tree()
    
    def save_current_project(self):
        """현재 프로젝트 저장"""
        if not self.mod_folder_path:
            QMessageBox.warning(self, "경고", "저장할 프로젝트가 없습니다.")
            return
        
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "프로젝트 저장", "프로젝트 이름:")
        if ok and name:
            self.projects[name] = {
                'path': self.mod_folder_path,
                'saved_at': datetime.now().isoformat()
            }
            self.save_projects()
            self.update_project_tree()
    
    def update_project_tree(self):
        """프로젝트 트리 업데이트"""
        self.project_tree.clear()
        for name, info in self.projects.items():
            item = QTreeWidgetItem([name, info['path'], info.get('saved_at', 'Unknown')])
            self.project_tree.addTopLevelItem(item)
    
    def load_projects(self):
        """프로젝트 목록 로드"""
        projects_str = self.settings.value('projects', '{}')
        try:
            return json.loads(projects_str)
        except:
            return {}
    
    def save_projects(self):
        """프로젝트 목록 저장"""
        self.settings.setValue('projects', json.dumps(self.projects))
    
    def open_gfx_file(self):
        """GFX 파일 열기"""
        current_item = self.gfx_tree.currentItem()
        if not current_item or not current_item.parent():
            return
        
        gfx_name = current_item.text(0)
        gfx_info = self.gfx_data.get(gfx_name)
        
        if gfx_info:
            try:
                if sys.platform == "win32":
                    os.startfile(gfx_info['file_source'])
                else:
                    subprocess.call(["xdg-open", gfx_info['file_source']])
            except Exception as e:
                QMessageBox.warning(self, "오류", f"파일을 열 수 없습니다: {str(e)}")
    
    def open_texture_folder(self):
        """텍스처 폴더 열기"""
        current_item = self.gfx_tree.currentItem()
        if not current_item or not current_item.parent():
            return
        
        gfx_name = current_item.text(0)
        gfx_info = self.gfx_data.get(gfx_name)
        
        if gfx_info:
            folder = os.path.dirname(gfx_info['texturefile'])
            try:
                if sys.platform == "win32":
                    os.startfile(folder)
                else:
                    subprocess.call(["xdg-open", folder])
            except Exception as e:
                QMessageBox.warning(self, "오류", f"폴더를 열 수 없습니다: {str(e)}")
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """드래그 진입 이벤트 처리"""
        if event.mimeData().hasUrls():
            # 이미지 파일인지 확인
            valid_files = []
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.dds', '.png', '.jpg', '.jpeg', '.bmp', '.tga')):
                    valid_files.append(file_path)
            
            if valid_files:
                event.acceptProposedAction()
                return
        
        event.ignore()
    
    def dropEvent(self, event: QDropEvent):
        """드롭 이벤트 처리"""
        if not self.mod_folder_path:
            QMessageBox.warning(self, "경고", "먼저 모드 폴더를 선택해주세요.")
            event.ignore()
            return
        
        if event.mimeData().hasUrls():
            # 이미지 파일들 수집
            image_files = []
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.dds', '.png', '.jpg', '.jpeg', '.bmp', '.tga')):
                    image_files.append(file_path)
            
            if image_files:
                self.process_dropped_images(image_files)
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()
    
    def process_dropped_images(self, image_files):
        """드롭된 이미지 파일들 처리"""
        gfx_files = list(Path(self.mod_folder_path).rglob("*.gfx"))
        if not gfx_files:
            QMessageBox.warning(self, "경고", "프로젝트에서 .gfx 파일을 찾을 수 없습니다.")
            return
        
        success_count = 0
        
        for image_file in image_files:
            dialog = DragDropDialog(self, image_file)
            # 모드 폴더 기준 상대 경로로 표시
            relative_paths = [os.path.relpath(str(f), self.mod_folder_path) for f in gfx_files]
            dialog.gfx_file_combo.addItems(relative_paths)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                data = dialog.get_data()
                if self.add_gfx_from_dragdrop(data):
                    success_count += 1
        
        if success_count > 0:
            self.scan_gfx_files()  # UI 새로고침
            QMessageBox.information(self, "완료", f"{success_count}개의 GFX가 성공적으로 추가되었습니다.")
    
    def add_gfx_from_dragdrop(self, data):
        """드래그 앤 드롭 데이터로 GFX 추가"""
        try:
            name = data['name']
            target_folder = data['target_folder']
            gfx_file = data['gfx_file']
            source_file = data['source_file']
            
            if not all([name, target_folder, gfx_file, source_file]):
                QMessageBox.warning(self, "오류", "모든 필드를 입력해주세요.")
                return False
            
            # 대상 폴더 생성
            target_full_path = os.path.join(self.mod_folder_path, target_folder)
            os.makedirs(target_full_path, exist_ok=True)
            
            # 파일 복사
            filename = os.path.basename(source_file)
            dest_file = os.path.join(target_full_path, filename)
            shutil.copy2(source_file, dest_file)
            
            # 상대 경로 생성
            relative_path = f"{target_folder}{filename}".replace('\\', '/')
            
            # GFX 파일에 추가
            self.save_gfx_to_file(name, relative_path, gfx_file)
            
            return True
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"GFX 추가 중 오류가 발생했습니다: {str(e)}")
            return False
    
    def handle_tree_drop(self, file_path, target_item):
        """트리 드롭 이벤트 처리"""
        if not self.mod_folder_path:
            QMessageBox.warning(self, "경고", "먼저 모드 폴더를 선택해주세요.")
            return
        
        # 드롭된 항목이 파일 노드인지 GFX 노드인지 확인
        if target_item.parent():
            # GFX 노드에 드롭 - 기존 GFX 교체
            self.handle_gfx_replacement(file_path, target_item)
        else:
            # 파일 노드에 드롭 - 새 GFX 자동 추가
            # Ctrl 키가 눌려있으면 수동 설정 모드
            modifiers = QApplication.keyboardModifiers()
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                self.handle_new_gfx_addition_manual(file_path, target_item)
            else:
                self.handle_new_gfx_addition(file_path, target_item)
    
    def handle_new_gfx_addition_manual(self, file_path, file_item):
        """파일 노드에 새 GFX 수동 추가 (Ctrl+드롭 시 사용)"""
        file_source = file_item.text(0)
        
        # GFX 파일 경로 찾기
        gfx_file_path = None
        for name, info in self.gfx_data.items():
            if info['file_source'] == file_source:
                gfx_file_path = info['file_source']
                break
        
        if not gfx_file_path:
            QMessageBox.warning(self, "오류", "대상 GFX 파일을 찾을 수 없습니다.")
            return
        
        # 드래그 앤 드롭 다이얼로그 열기 (수동 설정용)
        dialog = DragDropDialog(self, file_path)
        
        # GFX 파일을 자동으로 선택 (상대 경로로 비교)
        gfx_relative_path = os.path.relpath(gfx_file_path, self.mod_folder_path)
        for i in range(dialog.gfx_file_combo.count()):
            if gfx_relative_path == dialog.gfx_file_combo.itemText(i):
                dialog.gfx_file_combo.setCurrentIndex(i)
                break
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            data['source_file'] = file_path
            if self.add_gfx_from_dragdrop(data):
                self.scan_gfx_files()  # UI 새로고침
                QMessageBox.information(self, "완료", f"새 GFX '{data['name']}'가 성공적으로 추가되었습니다.")
    
    def handle_gfx_replacement(self, file_path, gfx_item):
        """기존 GFX 교체"""
        gfx_name = gfx_item.text(0)
        gfx_info = self.gfx_data.get(gfx_name)
        
        if not gfx_info:
            QMessageBox.warning(self, "오류", "선택된 GFX 정보를 찾을 수 없습니다.")
            return
        
        # 확인 다이얼로그
        result = QMessageBox.question(
            self, "GFX 교체 확인", 
            f"'{gfx_name}'의 텍스처를 새 이미지로 교체하시겠습니까?\n\n"
            f"현재: {gfx_info['relative_path']}\n"
            f"새 파일: {os.path.basename(file_path)}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if result == QMessageBox.StandardButton.Yes:
            # 대상 폴더 (기존 텍스처와 같은 폴더)
            current_texture_path = os.path.join(self.mod_folder_path, gfx_info['relative_path'])
            target_folder = os.path.dirname(current_texture_path)
            
            try:
                # 새 파일명 생성 (기존과 같은 이름 유지하거나 새 이름 사용)
                original_ext = os.path.splitext(gfx_info['relative_path'])[1]
                new_ext = os.path.splitext(file_path)[1]
                
                if original_ext.lower() == new_ext.lower():
                    # 같은 확장자면 기존 파일명 유지
                    dest_filename = os.path.basename(gfx_info['relative_path'])
                else:
                    # 다른 확장자면 새 파일명 사용
                    base_name = os.path.splitext(os.path.basename(gfx_info['relative_path']))[0]
                    dest_filename = base_name + new_ext
                
                dest_path = os.path.join(target_folder, dest_filename)
                
                # 파일 복사
                shutil.copy2(file_path, dest_path)
                
                # GFX 정의 업데이트 (필요한 경우)
                new_relative_path = os.path.relpath(dest_path, self.mod_folder_path).replace('\\', '/')
                if new_relative_path != gfx_info['relative_path']:
                    self.update_gfx_texture_path(gfx_name, new_relative_path, gfx_info['file_source'])
                
                # UI 새로고침
                self.scan_gfx_files()
                QMessageBox.information(self, "완료", f"'{gfx_name}' 텍스처가 성공적으로 교체되었습니다.")
                
            except Exception as e:
                QMessageBox.critical(self, "오류", f"파일 교체 중 오류가 발생했습니다: {str(e)}")
    
    def handle_new_gfx_addition(self, file_path, file_item):
        """파일 노드에 새 GFX 자동 추가"""
        file_source = file_item.text(0)
        
        # GFX 파일 경로 찾기
        gfx_file_path = None
        for name, info in self.gfx_data.items():
            if info['file_source'] == file_source:
                gfx_file_path = info['file_source']
                break
        
        if not gfx_file_path:
            QMessageBox.warning(self, "오류", "대상 GFX 파일을 찾을 수 없습니다.")
            return
        
        try:
            # 자동으로 GFX 이름 생성
            filename = Path(file_path).stem
            gfx_name = f"GFX_{filename}"
            
            # 중복 이름 체크 및 자동 번호 부여
            original_name = gfx_name
            counter = 1
            while gfx_name in self.gfx_data:
                gfx_name = f"{original_name}_{counter}"
                counter += 1
            
            # 자동으로 대상 폴더 결정 (기존 GFX 파일들과 같은 폴더 구조 사용)
            # GFX 파일의 폴더 구조 기반으로 적절한 하위폴더 찾기
            gfx_dir = os.path.dirname(gfx_file_path)
            
            # 기존 GFX들의 텍스처 경로 분석하여 적절한 폴더 찾기
            common_texture_folder = self.find_common_texture_folder(gfx_file_path)
            if common_texture_folder:
                target_folder = common_texture_folder
            else:
                # 기본값: gfx 파일과 같은 폴더에 gfx 하위폴더
                target_folder = os.path.join(gfx_dir, "gfx")
            
            # 대상 폴더 생성
            os.makedirs(target_folder, exist_ok=True)
            
            # 파일 복사
            filename_with_ext = os.path.basename(file_path)
            dest_file = os.path.join(target_folder, filename_with_ext)
            shutil.copy2(file_path, dest_file)
            
            # 상대 경로 생성
            relative_path = os.path.relpath(dest_file, self.mod_folder_path).replace('\\', '/')
            
            # GFX 파일에 추가
            gfx_relative_path = os.path.relpath(gfx_file_path, self.mod_folder_path)
            self.save_gfx_to_file(gfx_name, relative_path, gfx_relative_path)
            
            # UI 새로고침
            self.scan_gfx_files()
            
            # 성공 메시지 (더 간결하게)
            QMessageBox.information(
                self, "GFX 추가 완료", 
                f"새 GFX가 자동으로 추가되었습니다:\n\n"
                f"이름: {gfx_name}\n"
                f"파일: {relative_path}"
            )
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"자동 GFX 추가 중 오류가 발생했습니다: {str(e)}")
    
    def find_common_texture_folder(self, gfx_file_path):
        """GFX 파일의 기존 텍스처들이 저장된 공통 폴더 찾기"""
        texture_folders = []
        
        # 같은 GFX 파일의 모든 텍스처 경로 수집
        for name, info in self.gfx_data.items():
            if info['file_source'] == gfx_file_path and info['status'] == 'valid':
                texture_path = os.path.join(self.mod_folder_path, info['relative_path'])
                texture_folder = os.path.dirname(texture_path)
                if os.path.exists(texture_folder):
                    texture_folders.append(texture_folder)
        
        if not texture_folders:
            return None
            
        # 가장 많이 사용되는 폴더 찾기
        from collections import Counter
        folder_counts = Counter(texture_folders)
        most_common_folder = folder_counts.most_common(1)[0][0]
        
        return most_common_folder
    
    def update_gfx_texture_path(self, gfx_name, new_path, gfx_file_path):
        """GFX 정의의 텍스처 경로 업데이트"""
        try:
            with open(gfx_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 모드 폴더 기준 상대 경로로 변환
            if os.path.isabs(new_path):
                rel_new_path = os.path.relpath(new_path, self.mod_folder_path).replace('\\', '/')
            else:
                rel_new_path = new_path.replace('\\', '/')
            
            # GFX 정의 찾아서 texturefile 경로 교체 (대소문자 구분 없음)
            pattern = rf'({re.escape(gfx_name)}\s*=\s*\{{[^}}]*?)texturefile\s*=\s*"[^"]*"'
            replacement = rf'\1texturefile = "{rel_new_path}"'
            content = re.sub(pattern, replacement, content, flags=re.DOTALL | re.MULTILINE | re.IGNORECASE)
            
            with open(gfx_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
        except Exception as e:
            print(f"텍스처 경로 업데이트 중 오류: {str(e)}")
    
    def update_gui_preview_data(self):
        """GUI 프리뷰어에 GFX 데이터 전달"""
        # GFX 데이터를 GUI 프리뷰어가 기대하는 형식으로 변환
        # gfx_name -> image_path 매핑으로 변환
        preview_data = {}
        for name, info in self.gfx_data.items():
            if info['status'] == 'valid':  # 유효한 파일만 전달
                preview_data[name] = info['texturefile']
        
        self.gui_preview_widget.set_gfx_data(preview_data)
    
    def update_status(self):
        """상태바 업데이트"""
        if self.mod_folder_path:
            gfx_count = len(self.gfx_data)
            orphaned_count = len(self.orphaned_gfx) if hasattr(self, 'orphaned_gfx') else 0
            missing_count = len(self.missing_definitions) if hasattr(self, 'missing_definitions') else 0
            
            status_text = f"GFX: {gfx_count}개 | 미사용: {orphaned_count}개 | 누락: {missing_count}개 | 드래그 앤 드롭 지원"
            self.status_bar.showMessage(status_text)
        else:
            self.status_bar.showMessage("모드 폴더를 선택해주세요")


def main():
    """메인 함수"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # 애플리케이션 정보 설정
    app.setApplicationName("HOI4 GFX Manager")
    app.setApplicationVersion("2.1")
    app.setOrganizationName("HOI4 Modding Tools")
    
    window = GFXManager()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()