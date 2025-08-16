"""
HOI4 GUI 파일 프리뷰어 모듈

.gui 파일을 파싱하고 시각적으로 렌더링하여 미리보기를 제공합니다.

주요 기능:
- .gui 파일 파싱 (windowType, iconType, buttonType, instantTextBoxType 등)
- 시각적 GUI 레이아웃 렌더링
- GFX 이미지와 연동
- 좌표 시스템 처리
"""

import sys
import os
import re
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                            QPushButton, QLabel, QFileDialog, QScrollArea,
                            QFrame, QSplitter, QTextEdit, QTreeWidget, 
                            QTreeWidgetItem, QMainWindow, QTabWidget)
from PyQt6.QtCore import Qt, QRect, QPoint, QSize
from PyQt6.QtGui import QPainter, QPixmap, QColor, QFont, QPen, QBrush
from PIL import Image


@dataclass
class Position:
    """위치 정보를 담는 데이터 클래스"""
    x: int = 0
    y: int = 0


@dataclass
class Size:
    """크기 정보를 담는 데이터 클래스"""
    width: int = 100
    height: int = 100


@dataclass
class GUIElement:
    """GUI 요소의 기본 클래스"""
    name: str
    element_type: str
    position: Position
    size: Optional[Size] = None
    sprite_type: Optional[str] = None
    text: Optional[str] = None
    font: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    
    # HOI4 specific properties
    orientation: Optional[str] = None
    origo: Optional[str] = None
    margin: Optional[Dict[str, int]] = None
    clipping: Optional[bool] = None
    button_text: Optional[str] = None
    button_font: Optional[str] = None
    max_width: Optional[int] = None
    max_height: Optional[int] = None
    format_align: Optional[str] = None
    
    # Scripted GUI properties
    visible_condition: Optional[str] = None
    click_effect: Optional[str] = None
    is_dynamic: Optional[bool] = False


@dataclass 
class ScriptedGUIDefinition:
    """Scripted GUI 정의를 담는 데이터 클래스 (고도화된 HOI4 기능 지원)"""
    name: str
    window_name: str
    parent_window_name: Optional[str] = None
    context_type: Optional[str] = None
    
    # 기본 속성들
    visible_condition: Optional[str] = None
    triggers: Optional[Dict[str, str]] = None
    effects: Optional[Dict[str, str]] = None
    properties: Optional[Dict[str, Dict[str, str]]] = None
    
    # HOI4 고급 기능들
    ai_enabled: Optional[str] = None  # AI 활성화 조건
    dirty: Optional[str] = None  # 새로고침 변수
    moveable: Optional[bool] = None  # 이동 가능 여부
    resizable: Optional[bool] = None  # 크기 조절 가능 여부
    orientation: Optional[str] = None  # 정렬 방식
    
    # 애니메이션 관련
    animation_type: Optional[str] = None
    animation_time: Optional[float] = None
    upsound: Optional[str] = None  # 사운드 효과
    downsound: Optional[str] = None
    
    # 컨테이너 관련
    horizontalScrollbar: Optional[str] = None
    verticalScrollbar: Optional[str] = None
    smooth_scrolling: Optional[bool] = None
    
    # 포커스 및 입력 관련
    keyframe: Optional[Dict[str, str]] = None  # 키프레임 애니메이션
    input_handler: Optional[Dict[str, str]] = None  # 입력 처리
    
    # 고급 조건 및 스코프
    scope_conditions: Optional[Dict[str, str]] = None  # 스코프별 조건
    dynamic_lists: Optional[Dict[str, str]] = None  # 동적 리스트
    
    # 네스팅된 GUI 요소들
    nested_elements: Optional[Dict[str, Dict]] = None


class ScriptedGUIParser:
    """HOI4 scripted_gui 파일 파서"""
    
    def __init__(self):
        self.scripted_guis = []
        self.parse_errors = []
    
    def parse_file(self, file_path: str) -> List[ScriptedGUIDefinition]:
        """Scripted GUI 파일을 파싱하여 정의 목록 반환"""
        self.parse_errors = []
        
        try:
            if not os.path.exists(file_path):
                error_msg = f"File not found: {file_path}"
                self.parse_errors.append(error_msg)
                print(error_msg)
                return []
            
            try:
                with open(file_path, 'r', encoding='utf-8-sig') as file:
                    content = file.read()
            except UnicodeDecodeError:
                try:
                    with open(file_path, 'r', encoding='cp1252') as file:
                        content = file.read()
                except Exception as e:
                    error_msg = f"File encoding error: {e}"
                    self.parse_errors.append(error_msg)
                    print(error_msg)
                    return []
            
            if not content.strip():
                error_msg = "File is empty."
                self.parse_errors.append(error_msg)
                print(error_msg)
                return []
            
            # 주석 제거
            content = self._remove_comments(content)
            
            # scripted_gui 블록 찾기
            scripted_gui_pattern = r'scripted_gui\s*=\s*\{(.*)\}'
            gui_match = re.search(scripted_gui_pattern, content, re.DOTALL)
            
            if not gui_match:
                error_msg = "scripted_gui block not found. Please check if this is a valid scripted_gui file."
                self.parse_errors.append(error_msg)
                print(error_msg)
                return []
            
            gui_content = gui_match.group(1)
            
            # 각 GUI 정의 파싱
            self.scripted_guis = []
            self._parse_scripted_gui_definitions(gui_content)
            
            success_msg = f"Successfully parsed {len(self.scripted_guis)} scripted GUI definitions."
            print(success_msg)
            
            return self.scripted_guis
            
        except Exception as e:
            error_msg = f"Unexpected error during scripted_gui file parsing: {e}"
            self.parse_errors.append(error_msg)
            print(error_msg)
            return []
    
    def _remove_comments(self, content: str) -> str:
        """주석 제거"""
        lines = content.split('\n')
        cleaned_lines = []
        for line in lines:
            if '#' in line:
                line = line[:line.index('#')]
            cleaned_lines.append(line)
        return '\n'.join(cleaned_lines)
    
    def _parse_scripted_gui_definitions(self, content: str):
        """Scripted GUI 정의들을 파싱"""
        # 각 GUI 정의를 찾기 (예: KR_welcome_splash = { ... })
        gui_definitions = self._extract_gui_definitions(content)
        
        for gui_name, gui_content in gui_definitions.items():
            definition = self._parse_single_gui_definition(gui_name, gui_content)
            if definition:
                self.scripted_guis.append(definition)
    
    def _extract_gui_definitions(self, content: str) -> Dict[str, str]:
        """GUI 정의들을 추출"""
        definitions = {}
        
        # 패턴: gui_name = { ... }
        pattern = r'(\w+)\s*=\s*\{'
        
        start_pos = 0
        while True:
            match = re.search(pattern, content[start_pos:])
            if not match:
                break
                
            gui_name = match.group(1)
            block_start = start_pos + match.end() - 1  # '{' 포함
            brace_count = 1
            pos = block_start + 1
            
            # 중괄호 매칭으로 블록 끝 찾기
            while pos < len(content) and brace_count > 0:
                if content[pos] == '{':
                    brace_count += 1
                elif content[pos] == '}':
                    brace_count -= 1
                pos += 1
            
            if brace_count == 0:
                # 블록 내용 추출 (중괄호 제외)
                block_content = content[block_start + 1:pos - 1]
                definitions[gui_name] = block_content
            
            start_pos = pos
        
        return definitions
    
    def _parse_single_gui_definition(self, name: str, content: str) -> Optional[ScriptedGUIDefinition]:
        """단일 GUI 정의 파싱"""
        window_name = self._extract_property(content, 'window_name')
        if not window_name:
            return None
            
        parent_window_name = self._extract_property(content, 'parent_window_name')
        context_type = self._extract_property(content, 'context_type')
        
        # visible 조건 추출
        visible_condition = self._extract_block_property(content, 'visible')
        
        # triggers 추출
        triggers = self._extract_triggers(content)
        
        # effects 추출 
        effects = self._extract_effects(content)
        
        # properties 추출
        properties = self._extract_properties(content)
        
        # HOI4 고급 기능들 추출
        ai_enabled = self._extract_block_property(content, 'ai_enabled')
        dirty = self._extract_property(content, 'dirty')
        moveable = self._extract_boolean_property(content, 'moveable')
        resizable = self._extract_boolean_property(content, 'resizable')
        orientation = self._extract_property(content, 'orientation')
        
        # 애니메이션 관련
        animation_type = self._extract_property(content, 'animation_type')
        animation_time = self._extract_numeric_property(content, 'animation_time')
        upsound = self._extract_property(content, 'upsound')
        downsound = self._extract_property(content, 'downsound')
        
        # 컨테이너 관련
        horizontalScrollbar = self._extract_property(content, 'horizontalScrollbar')
        verticalScrollbar = self._extract_property(content, 'verticalScrollbar')
        smooth_scrolling = self._extract_boolean_property(content, 'smooth_scrolling')
        
        # 고급 블록들 추출
        keyframe = self._extract_keyframe_animations(content)
        input_handler = self._extract_input_handlers(content)
        scope_conditions = self._extract_scope_conditions(content)
        dynamic_lists = self._extract_dynamic_lists(content)
        nested_elements = self._extract_nested_elements(content)
        
        return ScriptedGUIDefinition(
            name=name,
            window_name=window_name,
            parent_window_name=parent_window_name,
            context_type=context_type,
            visible_condition=visible_condition,
            triggers=triggers,
            effects=effects,
            properties=properties,
            # 고급 기능들
            ai_enabled=ai_enabled,
            dirty=dirty,
            moveable=moveable,
            resizable=resizable,
            orientation=orientation,
            animation_type=animation_type,
            animation_time=animation_time,
            upsound=upsound,
            downsound=downsound,
            horizontalScrollbar=horizontalScrollbar,
            verticalScrollbar=verticalScrollbar,
            smooth_scrolling=smooth_scrolling,
            keyframe=keyframe,
            input_handler=input_handler,
            scope_conditions=scope_conditions,
            dynamic_lists=dynamic_lists,
            nested_elements=nested_elements
        )
    
    def _extract_property(self, content: str, prop_name: str) -> Optional[str]:
        """단순 속성 값 추출"""
        # More specific pattern to match exact property name
        # First try unquoted values
        pattern2 = rf'(?:^|\n)\s*{prop_name}\s*=\s*([^\s}}]+)'
        match = re.search(pattern2, content, re.MULTILINE)
        if match:
            value = match.group(1).strip()
            # Remove quotes if present
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            return value
        
        # Then try quoted values
        pattern1 = rf'(?:^|\n)\s*{prop_name}\s*=\s*["\']([^"\'}}]+)["\']'
        match = re.search(pattern1, content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        
        return None
    
    def _extract_block_property(self, content: str, prop_name: str) -> Optional[str]:
        """블록 속성 추출 (예: visible = { ... })"""
        pattern = rf'{prop_name}\s*=\s*\{{([^}}]*)\}}'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None
    
    def _extract_triggers(self, content: str) -> Optional[Dict[str, str]]:
        """triggers 블록 추출"""
        # triggers 블록을 extract_block_content 메서드로 추출
        triggers_blocks = self._extract_block_content_simple(content, 'triggers')
        
        if not triggers_blocks:
            return None
            
        triggers_content = triggers_blocks[0]  # 첫 번째 triggers 블록
        triggers = {}
        
        # 각 트리거 추출 (중첩 가능)
        trigger_pattern = r'(\w+)\s*=\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}'
        
        for match in re.finditer(trigger_pattern, triggers_content, re.DOTALL):
            trigger_name = match.group(1)
            trigger_condition = match.group(2).strip()
            triggers[trigger_name] = trigger_condition
        
        # 간단한 키-값 쌍도 찾기 (예: tab_2_visible = { tag_has_path_guide = yes })
        simple_pattern = r'(\w+)\s*=\s*\{([^{}]+)\}'
        for match in re.finditer(simple_pattern, triggers_content):
            trigger_name = match.group(1)
            trigger_condition = match.group(2).strip()
            if trigger_name not in triggers:  # 이미 복잡한 패턴으로 찾지 못한 경우만
                triggers[trigger_name] = trigger_condition
            
        return triggers if triggers else None
    
    def _extract_effects(self, content: str) -> Optional[Dict[str, str]]:
        """effects 블록 추출"""
        # effects 블록을 extract_block_content_simple 메서드로 추출
        effects_blocks = self._extract_block_content_simple(content, 'effects')
        
        if not effects_blocks:
            return None
            
        effects_content = effects_blocks[0]  # 첫 번째 effects 블록
        effects = {}
        
        # 각 이펙트 추출 (중첩 가능)
        effect_pattern = r'(\w+)\s*=\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}'
        
        for match in re.finditer(effect_pattern, effects_content, re.DOTALL):
            effect_name = match.group(1)
            effect_actions = match.group(2).strip()
            effects[effect_name] = effect_actions
        
        # 간단한 키-값 쌍도 찾기
        simple_pattern = r'(\w+)\s*=\s*\{([^{}]+)\}'
        for match in re.finditer(simple_pattern, effects_content):
            effect_name = match.group(1)
            effect_actions = match.group(2).strip()
            if effect_name not in effects:  # 이미 복잡한 패턴으로 찾지 못한 경우만
                effects[effect_name] = effect_actions
            
        return effects if effects else None
    
    def _extract_properties(self, content: str) -> Optional[Dict[str, Dict[str, str]]]:
        """properties 블록 추출"""
        properties_content = self._extract_block_property(content, 'properties')
        if not properties_content:
            return None
            
        properties = {}
        # 각 프로퍼티 추출 (예: element_name = { image = "..." })
        prop_pattern = r'(\w+)\s*=\s*\{([^{}]*)\}'
        
        for match in re.finditer(prop_pattern, properties_content):
            element_name = match.group(1)
            element_props = match.group(2).strip()
            
            # 프로퍼티 내부의 키-값 쌍 추출
            element_properties = {}
            kv_pattern = r'(\w+)\s*=\s*["\']?([^"\'}\s]+)["\']?'
            for kv_match in re.finditer(kv_pattern, element_props):
                key = kv_match.group(1)
                value = kv_match.group(2)
                element_properties[key] = value
                
            properties[element_name] = element_properties
            
        return properties if properties else None
    
    def _extract_block_content_simple(self, content: str, block_type: str) -> List[str]:
        """간단한 블록 추출 (기존 메서드와 동일하지만 단순화)"""
        blocks = []
        pattern = rf'{block_type}\s*=\s*\{{'
        
        start_pos = 0
        while True:
            match = re.search(pattern, content[start_pos:])
            if not match:
                break
            
            # 블록 시작 위치
            block_start = start_pos + match.end() - 1  # '{' 포함
            brace_count = 1
            pos = block_start + 1
            
            # 중괄호 매칭으로 블록 끝 찾기
            while pos < len(content) and brace_count > 0:
                if content[pos] == '{':
                    brace_count += 1
                elif content[pos] == '}':
                    brace_count -= 1
                pos += 1
            
            if brace_count == 0:
                # 블록 내용 추출 (중괄호 제외)
                block_content = content[block_start + 1:pos - 1]
                blocks.append(block_content)
            
            start_pos = pos
        
        return blocks
    
    def _extract_keyframe_animations(self, content: str) -> Optional[Dict[str, str]]:
        """키프레임 애니메이션 추출"""
        keyframes = {}
        keyframe_blocks = self._extract_block_content_simple(content, 'keyframe')
        
        for block in keyframe_blocks:
            # 각 키프레임 정의 추출
            lines = block.split('\n')
            for line in lines:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    keyframes[key.strip()] = value.strip()
        
        return keyframes if keyframes else None
    
    def _extract_input_handlers(self, content: str) -> Optional[Dict[str, str]]:
        """입력 핸들러 추출 (키보드, 마우스 이벤트)"""
        handlers = {}
        
        # 다양한 입력 핸들러 패턴들
        input_patterns = [
            'on_click', 'on_hover', 'on_focus', 'on_key_down', 'on_key_up',
            'shortcut', 'clicksound', 'over_sound', 'on_text_changed'
        ]
        
        for pattern in input_patterns:
            value = self._extract_property(content, pattern)
            if value:
                handlers[pattern] = value
                
        return handlers if handlers else None
    
    def _extract_scope_conditions(self, content: str) -> Optional[Dict[str, str]]:
        """스코프별 조건 추출 (THIS, ROOT, PREV 등)"""
        conditions = {}
        
        # 스코프 조건 패턴들
        scope_patterns = [
            'THIS', 'ROOT', 'PREV', 'FROM', 'FROMFROM',
            'scope_conditions', 'limit', 'any_of', 'all_of',
            'has_variable', 'check_variable', 'is_valid'
        ]
        
        for pattern in scope_patterns:
            # 블록 형태 조건
            block_condition = self._extract_block_property(content, pattern)
            if block_condition:
                conditions[pattern] = block_condition
            else:
                # 단순 값 조건
                simple_condition = self._extract_property(content, pattern)
                if simple_condition:
                    conditions[pattern] = simple_condition
                    
        return conditions if conditions else None
    
    def _extract_dynamic_lists(self, content: str) -> Optional[Dict[str, str]]:
        """동적 리스트 추출 (for_each, iterate 등)"""
        lists = {}
        
        # 동적 리스트 관련 패턴들
        list_patterns = [
            'for_each', 'iterate', 'dynamic_list', 'list_entry',
            'template', 'data_source', 'item_template'
        ]
        
        for pattern in list_patterns:
            block_data = self._extract_block_property(content, pattern)
            if block_data:
                lists[pattern] = block_data
                
        return lists if lists else None
    
    def _extract_nested_elements(self, content: str) -> Optional[Dict[str, Dict]]:
        """중첩된 GUI 요소들 추출"""
        elements = {}
        
        # 일반적인 GUI 요소 타입들
        element_types = [
            'containerWindowType', 'windowType', 'buttonType', 'iconType',
            'instantTextBoxType', 'editBoxType', 'checkboxType', 'scrollbarType',
            'listboxType', 'gridBoxType', 'positionType'
        ]
        
        for element_type in element_types:
            element_blocks = self._extract_block_content_simple(content, element_type)
            if element_blocks:
                elements[element_type] = {}
                for i, block_content in enumerate(element_blocks):
                    # 요소 이름 추출
                    name = self._extract_property(block_content, 'name')
                    if name:
                        elements[element_type][name] = {
                            'content': block_content,
                            'type': element_type
                        }
                    else:
                        # 이름이 없으면 인덱스 사용
                        elements[element_type][f'{element_type}_{i}'] = {
                            'content': block_content,
                            'type': element_type
                        }
        
        return elements if elements else None
    
    def _extract_advanced_conditions(self, content: str) -> Optional[Dict[str, str]]:
        """고급 조건문 추출 (if, else, switch 등)"""
        conditions = {}
        
        # 고급 조건 패턴들
        advanced_patterns = [
            'if', 'else_if', 'else', 'switch', 'case', 'default',
            'limit', 'modifier', 'tooltip', 'custom_tooltip'
        ]
        
        for pattern in advanced_patterns:
            block_data = self._extract_block_property(content, pattern)
            if block_data:
                conditions[pattern] = block_data
                
        return conditions if conditions else None
    
    def _extract_localization_keys(self, content: str) -> Optional[Dict[str, str]]:
        """현지화 키 추출"""
        loc_keys = {}
        
        # 텍스트가 현지화 키인지 확인하는 패턴 (대문자와 언더스코어)
        loc_pattern = r'([A-Z_][A-Z0-9_]*)'
        
        # 텍스트 관련 속성들에서 현지화 키 찾기
        text_properties = ['text', 'buttonText', 'tooltip', 'title', 'description']
        
        for prop in text_properties:
            value = self._extract_property(content, prop)
            if value and re.match(loc_pattern, value.replace('"', '')):
                loc_keys[prop] = value.replace('"', '')
                
        return loc_keys if loc_keys else None
    
    def _extract_boolean_property(self, content: str, prop_name: str) -> Optional[bool]:
        """불린 속성 추출"""
        pattern = rf'{prop_name}\s*=\s*(yes|no|true|false)'
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            value = match.group(1).lower()
            return value in ['yes', 'true']
        return None
    
    def _extract_numeric_property(self, content: str, prop_name: str) -> Optional[float]:
        """숫자 속성 추출 (정수 및 소수 지원)"""
        pattern = rf'{prop_name}\s*=\s*([+-]?(?:\d+\.?\d*|\.\d+))'
        match = re.search(pattern, content)
        if match:
            return float(match.group(1))
        return None


class HOI4GUIParser:
    """HOI4 .gui 파일 파서"""
    
    def __init__(self):
        self.elements = []
        self.window_size = Size(800, 600)  # 기본 윈도우 크기
        self.scripted_gui_data = {}  # scripted_gui 데이터 저장
    
    def set_scripted_gui_data(self, scripted_gui_definitions: List[ScriptedGUIDefinition]):
        """Scripted GUI 데이터 설정"""
        self.scripted_gui_data = {}
        for definition in scripted_gui_definitions:
            self.scripted_gui_data[definition.window_name] = definition
    
    def parse_file(self, file_path: str) -> List[GUIElement]:
        """GUI 파일을 파싱하여 요소 목록 반환"""
        self.parse_errors = []  # 파싱 오류 목록 초기화
        
        try:
            # 파일 존재 확인
            if not os.path.exists(file_path):
                error_msg = f"File not found: {file_path}"
                self.parse_errors.append(error_msg)
                print(error_msg)
                return []
            
            # 파일 읽기
            try:
                with open(file_path, 'r', encoding='utf-8-sig') as file:
                    content = file.read()
            except UnicodeDecodeError:
                try:
                    with open(file_path, 'r', encoding='cp1252') as file:
                        content = file.read()
                except Exception as e:
                    error_msg = f"File encoding error: {e}"
                    self.parse_errors.append(error_msg)
                    print(error_msg)
                    return []
            
            if not content.strip():
                error_msg = "File is empty."
                self.parse_errors.append(error_msg)
                print(error_msg)
                return []
            
            # 주석 제거
            content = self._remove_comments(content)
            
            # guiTypes 블록 찾기
            gui_types_pattern = r'guiTypes\s*=\s*\{(.*)\}'
            gui_match = re.search(gui_types_pattern, content, re.DOTALL)
            
            if not gui_match:
                error_msg = "guiTypes block not found. Please check if this is a valid HOI4 GUI file."
                self.parse_errors.append(error_msg)
                print(error_msg)
                return []
            
            gui_content = gui_match.group(1)
            
            # 각 GUI 요소 파싱
            self.elements = []
            element_count_before = len(self.elements)
            self._parse_elements(gui_content)
            
            # Scripted GUI 정보를 요소에 적용
            self._apply_scripted_gui_data()
            
            element_count_after = len(self.elements)
            
            success_msg = f"Successfully parsed {element_count_after} GUI elements."
            if self.scripted_gui_data:
                success_msg += f" (with {len(self.scripted_gui_data)} scripted GUI definitions applied)"
            print(success_msg)
            
            return self.elements
            
        except Exception as e:
            error_msg = f"Unexpected error during GUI file parsing: {e}"
            self.parse_errors.append(error_msg)
            print(error_msg)
            return []
    
    def _remove_comments(self, content: str) -> str:
        """주석 제거"""
        lines = content.split('\n')
        cleaned_lines = []
        for line in lines:
            if '#' in line:
                line = line[:line.index('#')]
            cleaned_lines.append(line)
        return '\n'.join(cleaned_lines)
    
    def _parse_elements(self, content: str):
        """GUI 요소들을 파싱"""
        # 이미 파싱된 요소들을 추적하기 위한 집합 초기화
        self.parsed_elements = set()
        
        # containerWindowType 파싱 (가장 중요) - 이것만 사용하고 중첩 파싱에 의존
        self._parse_container_window_types(content)
        
        # 최상위 레벨의 다른 요소들도 파싱 (containerWindowType 밖에 있는 것들)
        self._parse_top_level_elements(content)
    
    def _parse_container_window_types(self, content: str):
        """containerWindowType 요소들 파싱 (HOI4의 메인 컨테이너)"""
        # 중첩된 containerWindowType을 포함한 더 강력한 파싱
        containers = self._extract_block_content(content, "containerWindowType")
        
        for container_content in containers:
            element = self._parse_container_window_element(container_content)
            if element and not self._is_duplicate(element):
                self.elements.append(element)
                self._mark_as_parsed(element)
                # 첫 번째 컨테이너의 크기를 전체 크기로 설정
                if len(self.elements) == 1 and element.size:
                    self.window_size = element.size
            
            # 중첩된 요소들도 파싱
            self._parse_nested_elements(container_content)
    
    def _parse_top_level_elements(self, content: str):
        """최상위 레벨의 요소들 파싱 (containerWindowType 밖에 있는 것들)"""
        # windowType 파싱
        self._parse_window_types(content)
        
        # 기타 요소들 (중복 방지를 위해 simple parsing 사용)
        self._parse_checkbox_types(content)
        self._parse_scrollbar_types(content)
        self._parse_gridbox_types(content)
        self._parse_listbox_types(content)
        self._parse_editbox_types(content)
    
    def _parse_window_types(self, content: str):
        """windowType 요소들 파싱"""
        pattern = r'windowType\s*=\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}'
        matches = re.findall(pattern, content, re.DOTALL)
        
        for match in matches:
            element = self._parse_window_element(match)
            if element:
                self.elements.append(element)
                # 첫 번째 윈도우의 크기를 전체 크기로 설정
                if len(self.elements) == 1 and element.size:
                    self.window_size = element.size
    
    def _parse_icon_types(self, content: str):
        """iconType 요소들 파싱"""
        pattern = r'iconType\s*=\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}'
        matches = re.findall(pattern, content, re.DOTALL)
        
        for match in matches:
            element = self._parse_icon_element(match)
            if element:
                self.elements.append(element)
    
    def _parse_button_types(self, content: str):
        """buttonType 요소들 파싱"""
        pattern = r'buttonType\s*=\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}'
        matches = re.findall(pattern, content, re.DOTALL)
        
        for match in matches:
            element = self._parse_button_element(match)
            if element:
                self.elements.append(element)
    
    def _parse_text_box_types(self, content: str):
        """instantTextBoxType 요소들 파싱"""
        # Case insensitive to handle both instantTextBoxType and instantTextboxType
        textboxes = self._extract_block_content(content, r'(?i)instantTextboxType')
        
        for textbox_content in textboxes:
            element = self._parse_text_box_element(textbox_content)
            if element:
                self.elements.append(element)
    
    def _parse_container_window_element(self, content: str) -> Optional[GUIElement]:
        """containerWindowType 요소 파싱 (HOI4의 메인 컨테이너)"""
        name = self._extract_property(content, 'name')
        position = self._extract_position(content)
        size = self._extract_size(content)
        
        # background 속성 파싱 (여러 형태 지원)
        sprite_type = self._extract_background_sprite(content)
        
        # HOI4 특수 속성들
        orientation = self._extract_property(content, 'orientation')
        origo = self._extract_property(content, 'origo')
        margin = self._extract_margin(content)
        clipping = self._extract_boolean_property(content, 'clipping')
        
        if name:
            return GUIElement(
                name=name,
                element_type='containerWindowType',
                position=position,
                size=size,
                sprite_type=sprite_type,
                orientation=orientation,
                origo=origo,
                margin=margin,
                clipping=clipping
            )
        return None
    
    def _parse_window_element(self, content: str) -> Optional[GUIElement]:
        """windowType 요소 파싱"""
        name = self._extract_property(content, 'name')
        position = self._extract_position(content)
        size = self._extract_size(content)
        
        # background spriteType 찾기
        bg_pattern = r'background\s*=\s*\{[^{}]*spriteType\s*=\s*["\']?([^"\'}\s]+)["\']?[^{}]*\}'
        bg_match = re.search(bg_pattern, content)
        sprite_type = bg_match.group(1) if bg_match else None
        
        if name:
            return GUIElement(
                name=name,
                element_type='windowType',
                position=position,
                size=size,
                sprite_type=sprite_type
            )
        return None
    
    def _parse_icon_element(self, content: str) -> Optional[GUIElement]:
        """iconType 요소 파싱"""
        name = self._extract_property(content, 'name')
        position = self._extract_position(content)
        sprite_type = self._extract_property(content, 'spriteType')
        
        # quadTextureSprite도 지원
        if not sprite_type:
            sprite_type = self._extract_property(content, 'quadTextureSprite')
        
        if name:
            return GUIElement(
                name=name,
                element_type='iconType',
                position=position,
                sprite_type=sprite_type
            )
        return None
    
    def _parse_button_element(self, content: str) -> Optional[GUIElement]:
        """buttonType 요소 파싱"""
        name = self._extract_property(content, 'name')
        position = self._extract_position(content)
        size = self._extract_size(content)
        
        # quadTextureSprite 또는 spriteType 찾기
        sprite_patterns = [
            r'quadTextureSprite\s*=\s*["\']?([^"\'}\s]+)["\']?',
            r'spriteType\s*=\s*["\']?([^"\'}\s]+)["\']?'
        ]
        
        sprite_type = None
        for pattern in sprite_patterns:
            match = re.search(pattern, content)
            if match:
                sprite_type = match.group(1)
                break
        
        # 버튼 텍스트 및 폰트
        button_text = self._extract_property(content, 'buttonText')
        button_font = self._extract_property(content, 'buttonFont')
        orientation = self._extract_property(content, 'orientation')
        
        if name:
            return GUIElement(
                name=name,
                element_type='buttonType',
                position=position,
                size=size,
                sprite_type=sprite_type,
                button_text=button_text,
                button_font=button_font,
                orientation=orientation
            )
        return None
    
    def _parse_text_box_element(self, content: str) -> Optional[GUIElement]:
        """instantTextBoxType 요소 파싱"""
        name = self._extract_property(content, 'name')
        position = self._extract_position(content)
        text = self._extract_property(content, 'text')
        font = self._extract_property(content, 'font')
        
        # HOI4 텍스트 속성들
        max_width = self._extract_numeric_property(content, 'maxWidth')
        max_height = self._extract_numeric_property(content, 'maxHeight')
        format_align = self._extract_property(content, 'format')
        orientation = self._extract_property(content, 'orientation')
        
        if name:
            return GUIElement(
                name=name,
                element_type='instantTextBoxType',
                position=position,
                text=text,
                font=font,
                max_width=max_width,
                max_height=max_height,
                format_align=format_align,
                orientation=orientation
            )
        return None
    
    def _parse_checkbox_types(self, content: str):
        """checkboxType 요소들 파싱"""
        pattern = r'checkboxType\s*=\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}'
        matches = re.findall(pattern, content, re.DOTALL)
        
        for match in matches:
            element = self._parse_checkbox_element(match)
            if element:
                self.elements.append(element)
    
    def _parse_scrollbar_types(self, content: str):
        """scrollbarType 요소들 파싱"""
        pattern = r'scrollbarType\s*=\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}'
        matches = re.findall(pattern, content, re.DOTALL)
        
        for match in matches:
            element = self._parse_scrollbar_element(match)
            if element:
                self.elements.append(element)
    
    def _parse_gridbox_types(self, content: str):
        """gridBoxType 요소들 파싱"""
        pattern = r'gridBoxType\s*=\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}'
        matches = re.findall(pattern, content, re.DOTALL)
        
        for match in matches:
            element = self._parse_gridbox_element(match)
            if element:
                self.elements.append(element)
    
    def _parse_checkbox_element(self, content: str) -> Optional[GUIElement]:
        """checkboxType 요소 파싱"""
        name = self._extract_property(content, 'name')
        position = self._extract_position(content)
        sprite_type = self._extract_property(content, 'spriteType')
        
        if name:
            return GUIElement(
                name=name,
                element_type='checkboxType',
                position=position,
                size=Size(24, 24),  # 기본 체크박스 크기
                sprite_type=sprite_type
            )
        return None
    
    def _parse_scrollbar_element(self, content: str) -> Optional[GUIElement]:
        """scrollbarType 요소 파싱"""
        name = self._extract_property(content, 'name')
        position = self._extract_position(content)
        size = self._extract_size(content)
        
        if name:
            return GUIElement(
                name=name,
                element_type='scrollbarType',
                position=position,
                size=size or Size(20, 200)  # 기본 스크롤바 크기
            )
        return None
    
    def _parse_gridbox_element(self, content: str) -> Optional[GUIElement]:
        """gridBoxType 요소 파싱"""
        name = self._extract_property(content, 'name')
        position = self._extract_position(content)
        size = self._extract_size(content)
        
        if name:
            return GUIElement(
                name=name,
                element_type='gridBoxType',
                position=position,
                size=size or Size(300, 200)  # 기본 그리드박스 크기
            )
        return None
    
    def _parse_listbox_types(self, content: str):
        """listboxType 요소들 파싱"""
        pattern = r'listboxType\s*=\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}'
        matches = re.findall(pattern, content, re.DOTALL)
        
        for match in matches:
            element = self._parse_listbox_element(match)
            if element:
                self.elements.append(element)
    
    def _parse_editbox_types(self, content: str):
        """editboxType 요소들 파싱"""
        pattern = r'editboxType\s*=\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}'
        matches = re.findall(pattern, content, re.DOTALL)
        
        for match in matches:
            element = self._parse_editbox_element(match)
            if element:
                self.elements.append(element)
    
    def _parse_listbox_element(self, content: str) -> Optional[GUIElement]:
        """listboxType 요소 파싱"""
        name = self._extract_property(content, 'name')
        position = self._extract_position(content)
        size = self._extract_size(content)
        
        if name:
            return GUIElement(
                name=name,
                element_type='listboxType',
                position=position,
                size=size or Size(200, 100)  # 기본 리스트박스 크기
            )
        return None
    
    def _parse_editbox_element(self, content: str) -> Optional[GUIElement]:
        """editboxType 요소 파싱"""
        name = self._extract_property(content, 'name')
        position = self._extract_position(content)
        size = self._extract_size(content)
        text = self._extract_property(content, 'text')
        
        if name:
            return GUIElement(
                name=name,
                element_type='editboxType',
                position=position,
                size=size or Size(150, 25),  # 기본 에디트박스 크기
                text=text
            )
        return None
    
    def _extract_property(self, content: str, prop_name: str) -> Optional[str]:
        """속성 값 추출 (HOI4 형식 지원)"""
        # 따옴표가 있는 경우
        pattern1 = rf'{prop_name}\s*=\s*["\']([^"\'}}]+)["\']'
        match = re.search(pattern1, content)
        if match:
            return match.group(1).strip()
        
        # 따옴표가 없는 경우
        pattern2 = rf'{prop_name}\s*=\s*([^\s}}]+)'
        match = re.search(pattern2, content)
        if match:
            return match.group(1).strip()
        
        return None
    
    def _extract_background_sprite(self, content: str) -> Optional[str]:
        """background 속성에서 sprite 추출 (HOI4 다양한 형식 지원)"""
        # background = { spriteType = "..." } 형식
        bg_sprite_pattern = r'background\s*=\s*\{\s*spriteType\s*=\s*["\']?([^"\'}\s]+)["\']?[^}]*\}'
        match = re.search(bg_sprite_pattern, content)
        if match:
            return match.group(1)
        
        # background = { quadTextureSprite = "..." } 형식
        bg_quad_pattern = r'background\s*=\s*\{\s*quadTextureSprite\s*=\s*["\']?([^"\'}\s]+)["\']?[^}]*\}'
        match = re.search(bg_quad_pattern, content)
        if match:
            return match.group(1)
        
        # 단순한 background = "..." 형식
        bg_simple_pattern = r'background\s*=\s*["\']?([^"\'}\s]+)["\']?'
        match = re.search(bg_simple_pattern, content)
        if match:
            return match.group(1)
        
        return None
    
    def _extract_margin(self, content: str) -> Optional[Dict[str, int]]:
        """margin 속성 추출"""
        margin_pattern = r'margin\s*=\s*\{[^}]*left\s*=\s*(\d+)[^}]*right\s*=\s*(\d+)[^}]*\}'
        match = re.search(margin_pattern, content)
        if match:
            return {
                'left': int(match.group(1)),
                'right': int(match.group(2))
            }
        return None
    
    def _extract_boolean_property(self, content: str, prop_name: str) -> Optional[bool]:
        """불린 속성 추출"""
        pattern = rf'{prop_name}\s*=\s*(yes|no|true|false)'
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            value = match.group(1).lower()
            return value in ['yes', 'true']
        return None
    
    def _extract_numeric_property(self, content: str, prop_name: str) -> Optional[int]:
        """숫자 속성 추출"""
        pattern = rf'{prop_name}\s*=\s*(\d+)'
        match = re.search(pattern, content)
        if match:
            return int(match.group(1))
        return None
    
    def _extract_position(self, content: str) -> Position:
        """position 속성 추출 (HOI4는 다양한 형식 지원)"""
        # 기본 x=N y=N 형식
        pos_pattern = r'position\s*=\s*\{\s*x\s*=\s*([+-]?\d+)\s*y\s*=\s*([+-]?\d+)\s*\}'
        match = re.search(pos_pattern, content)
        if match:
            return Position(int(match.group(1)), int(match.group(2)))
        
        # 간단한 x=N y=N 형식 (중괄호 없음)
        simple_pattern = r'position\s*=\s*\{\s*([+-]?\d+)\s+([+-]?\d+)\s*\}'
        match = re.search(simple_pattern, content)
        if match:
            return Position(int(match.group(1)), int(match.group(2)))
        
        return Position()
    
    def _extract_size(self, content: str) -> Optional[Size]:
        """size 속성 추출 (HOI4는 다양한 형식 지원)"""
        # 기본 width=N height=N 형식
        size_pattern = r'size\s*=\s*\{\s*width\s*=\s*(\d+)\s*height\s*=\s*(\d+)\s*\}'
        match = re.search(size_pattern, content)
        if match:
            return Size(int(match.group(1)), int(match.group(2)))
        
        # 간단한 N N 형식
        simple_pattern = r'size\s*=\s*\{\s*(\d+)\s+(\d+)\s*\}'
        match = re.search(simple_pattern, content)
        if match:
            return Size(int(match.group(1)), int(match.group(2)))
        
        return None
    
    def _extract_block_content(self, content: str, block_type: str) -> List[str]:
        """중첩된 블록을 올바르게 추출하는 개선된 방법"""
        blocks = []
        # Support both plain strings and regex patterns
        if block_type.startswith('(?i)'):
            # Handle case insensitive regex
            clean_pattern = block_type[4:]  # Remove (?i) prefix
            pattern = rf'{clean_pattern}\s*=\s*\{{'
            search_flags = re.IGNORECASE
        else:
            pattern = rf'{block_type}\s*=\s*\{{'
            search_flags = 0
        
        start_pos = 0
        while True:
            match = re.search(pattern, content[start_pos:], search_flags)
            if not match:
                break
            
            # 블록 시작 위치
            block_start = start_pos + match.end() - 1  # '{' 포함
            brace_count = 1
            pos = block_start + 1
            
            # 중괄호 매칭으로 블록 끝 찾기
            while pos < len(content) and brace_count > 0:
                if content[pos] == '{':
                    brace_count += 1
                elif content[pos] == '}':
                    brace_count -= 1
                pos += 1
            
            if brace_count == 0:
                # 블록 내용 추출 (중괄호 제외)
                block_content = content[block_start + 1:pos - 1]
                blocks.append(block_content)
            
            start_pos = pos
        
        return blocks
    
    def _get_element_key(self, element: GUIElement) -> str:
        """요소의 고유 키 생성 (중복 방지용)"""
        return f"{element.element_type}:{element.name}:{element.position.x}:{element.position.y}"
    
    def _is_duplicate(self, element: GUIElement) -> bool:
        """요소가 이미 파싱되었는지 확인"""
        return self._get_element_key(element) in self.parsed_elements
    
    def _mark_as_parsed(self, element: GUIElement):
        """요소를 파싱됨으로 표시"""
        self.parsed_elements.add(self._get_element_key(element))
    
    def _parse_nested_elements(self, content: str):
        """중첩된 요소들 파싱"""
        # 중첩된 containerWindowType (재귀 방지를 위해 한 레벨만)
        nested_containers = self._extract_block_content(content, 'containerWindowType')
        for container_content in nested_containers:
            element = self._parse_container_window_element(container_content)
            if element and not self._is_duplicate(element):
                self.elements.append(element)
                self._mark_as_parsed(element)
                # 더 깊은 중첩을 위해 재귀 호출 (하지만 중복 방지)
                self._parse_nested_elements(container_content)
        
        # 중첩된 다른 요소들 (중복 방지를 위해 간단한 패턴 사용)
        # iconType 파싱
        icons = self._extract_block_content(content, 'iconType')
        for icon_content in icons:
            element = self._parse_icon_element(icon_content)
            if element and not self._is_duplicate(element):
                self.elements.append(element)
                self._mark_as_parsed(element)
        
        # buttonType 파싱
        buttons = self._extract_block_content(content, 'buttonType')
        for button_content in buttons:
            element = self._parse_button_element(button_content)
            if element and not self._is_duplicate(element):
                self.elements.append(element)
                self._mark_as_parsed(element)
        
        # instantTextboxType 파싱 (case insensitive)
        textboxes = self._extract_block_content(content, '(?i)instantTextboxType')
        for textbox_content in textboxes:
            element = self._parse_text_box_element(textbox_content)
            if element and not self._is_duplicate(element):
                self.elements.append(element)
                self._mark_as_parsed(element)
    
    def _apply_scripted_gui_data(self):
        """Scripted GUI 데이터를 요소에 적용"""
        if not self.scripted_gui_data:
            return
            
        for element in self.elements:
            # 컨테이너 요소에 대해 scripted GUI 정보 찾기
            if element.element_type == 'containerWindowType':
                # 직접 매칭
                scripted_gui = self.scripted_gui_data.get(element.name)
                if scripted_gui:
                    element.visible_condition = scripted_gui.visible_condition
                    element.is_dynamic = True
                    
                    # 고급 scripted_gui 데이터 연결
                    element.scripted_data = self._create_scripted_data_dict(scripted_gui)
                    
                    # 프로퍼티 적용
                    if scripted_gui.properties:
                        element.properties = element.properties or {}
                        element.properties.update(scripted_gui.properties)
                
                # window_name으로도 찾기
                for scripted_gui in self.scripted_gui_data.values():
                    if scripted_gui.window_name == element.name:
                        element.visible_condition = scripted_gui.visible_condition
                        element.is_dynamic = True
                        element.scripted_data = self._create_scripted_data_dict(scripted_gui)
                        break
            
            # 버튼, 아이콘 등에 대해 trigger 및 effect 정보 찾기
            elif element.element_type in ['buttonType', 'iconType', 'instantTextBoxType']:
                element_matched = False
                for scripted_gui in self.scripted_gui_data.values():
                    if scripted_gui.triggers:
                        # 다양한 패턴으로 트리거 찾기
                        patterns = [
                            f"{element.name}_click_enabled",
                            f"{element.name}_visible", 
                            element.name + "_visible",
                            element.name + "_click_enabled"
                        ]
                        
                        for pattern in patterns:
                            if pattern in scripted_gui.triggers:
                                element.visible_condition = scripted_gui.triggers[pattern]
                                element.is_dynamic = True
                                element_matched = True
                                break
                    
                    if scripted_gui.effects and not element_matched:
                        # 클릭 이펙트 찾기
                        click_patterns = [
                            f"{element.name}_click",
                            element.name + "_click"
                        ]
                        
                        for pattern in click_patterns:
                            if pattern in scripted_gui.effects:
                                element.click_effect = scripted_gui.effects[pattern]
                                element.is_dynamic = True
                                element_matched = True
                                break
                    
                    if element_matched:
                        # 매칭된 요소에 고급 데이터 연결
                        element.scripted_data = self._create_scripted_data_dict(scripted_gui)
                        break
    
    def _create_scripted_data_dict(self, scripted_gui: ScriptedGUIDefinition) -> Dict[str, any]:
        """ScriptedGUIDefinition을 딕셔너리로 변환하여 렌더링에서 사용"""
        data = {}
        
        # 기본 속성들
        if scripted_gui.ai_enabled:
            data['ai_enabled'] = scripted_gui.ai_enabled
        if scripted_gui.dirty:
            data['dirty'] = scripted_gui.dirty
        if scripted_gui.moveable is not None:
            data['moveable'] = scripted_gui.moveable
        if scripted_gui.orientation:
            data['orientation'] = scripted_gui.orientation
        
        # 애니메이션 관련
        if scripted_gui.animation_type:
            data['animation_type'] = scripted_gui.animation_type
        if scripted_gui.animation_time is not None:
            data['animation_time'] = scripted_gui.animation_time
        if scripted_gui.upsound:
            data['upsound'] = scripted_gui.upsound
        if scripted_gui.downsound:
            data['downsound'] = scripted_gui.downsound
        
        # 고급 기능들
        if scripted_gui.keyframe:
            data['keyframe'] = scripted_gui.keyframe
        if scripted_gui.input_handler:
            data['input_handler'] = scripted_gui.input_handler
        if scripted_gui.scope_conditions:
            data['scope_conditions'] = scripted_gui.scope_conditions
        if scripted_gui.dynamic_lists:
            data['dynamic_lists'] = scripted_gui.dynamic_lists
        if scripted_gui.nested_elements:
            data['nested_elements'] = scripted_gui.nested_elements
        
        return data


class GUIPreviewCanvas(QWidget):
    """GUI 미리보기를 렌더링하는 캔버스"""
    
    def __init__(self, gfx_data: Dict[str, str] = None):
        super().__init__()
        self.elements = []
        self.gfx_data = gfx_data or {}  # GFX 이름 -> 이미지 경로 매핑
        self.window_size = Size(800, 600)
        self.scale_factor = 1.0
        self.setMinimumSize(400, 300)
        
        # 컨텍스트 메뉴 설정
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        # 캔버스 스타일링
        self.setStyleSheet("""
            GUIPreviewCanvas {
                background-color: #2c3e50;
                border: 1px solid gray;
            }
        """)
    
    def set_elements(self, elements: List[GUIElement], window_size: Size):
        """렌더링할 요소들 설정"""
        self.elements = elements
        self.window_size = window_size
        self.calculate_scale_factor()
        self.update()
    
    def calculate_scale_factor(self):
        """캔버스 크기에 맞는 스케일 팩터 계산"""
        if self.window_size.width > 0 and self.window_size.height > 0:
            widget_size = self.size()
            scale_x = (widget_size.width() - 40) / self.window_size.width
            scale_y = (widget_size.height() - 40) / self.window_size.height
            self.scale_factor = min(scale_x, scale_y, 1.0)  # 최대 1.0으로 제한
    
    def resizeEvent(self, event):
        """위젯 크기 변경 시 스케일 재계산"""
        super().resizeEvent(event)
        self.calculate_scale_factor()
        self.update()
    
    def paintEvent(self, event):
        """GUI 요소들을 그리기"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 배경 그리기
        painter.fillRect(self.rect(), QColor(44, 62, 80))
        
        if not self.elements:
            # 요소가 없을 때 안내 메시지
            painter.setPen(QColor(149, 165, 166))
            painter.setFont(QFont("Arial", 14))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 
                           "GUI 파일을 선택하여 미리보기를 확인하세요")
            return
        
        # 변환 행렬 설정 (스케일링 및 중앙 정렬)
        painter.save()
        
        # 중앙 정렬을 위한 오프셋 계산
        scaled_width = self.window_size.width * self.scale_factor
        scaled_height = self.window_size.height * self.scale_factor
        offset_x = (self.width() - scaled_width) / 2
        offset_y = (self.height() - scaled_height) / 2
        
        painter.translate(offset_x, offset_y)
        painter.scale(self.scale_factor, self.scale_factor)
        
        # GUI 요소들 렌더링
        for element in self.elements:
            self._render_element(painter, element)
        
        painter.restore()
        
        # 스케일 정보 표시
        painter.setPen(QColor(236, 240, 241))
        painter.setFont(QFont("Arial", 10))
        scale_text = f"Scale: {self.scale_factor:.2f} | Size: {self.window_size.width}x{self.window_size.height}"
        painter.drawText(10, 20, scale_text)
    
    def _render_element(self, painter: QPainter, element: GUIElement):
        """개별 GUI 요소 렌더링"""
        if element.element_type == 'containerWindowType':
            self._render_container_window(painter, element)
        elif element.element_type == 'windowType':
            self._render_window(painter, element)
        elif element.element_type == 'iconType':
            self._render_icon(painter, element)
        elif element.element_type == 'buttonType':
            self._render_button(painter, element)
        elif element.element_type == 'instantTextBoxType':
            self._render_text_box(painter, element)
        elif element.element_type == 'checkboxType':
            self._render_checkbox(painter, element)
        elif element.element_type == 'scrollbarType':
            self._render_scrollbar(painter, element)
        elif element.element_type == 'gridBoxType':
            self._render_gridbox(painter, element)
        elif element.element_type == 'listboxType':
            self._render_listbox(painter, element)
        elif element.element_type == 'editboxType':
            self._render_editbox(painter, element)
    
    def _render_window(self, painter: QPainter, element: GUIElement):
        """windowType 렌더링"""
        x, y = element.position.x, element.position.y
        
        if element.size:
            width, height = element.size.width, element.size.height
        else:
            width, height = self.window_size.width, self.window_size.height
        
        # 배경 이미지가 있는 경우
        if element.sprite_type and element.sprite_type in self.gfx_data:
            pixmap = self._load_gfx_image(element.sprite_type)
            if pixmap:
                # 이미지를 윈도우 크기에 맞게 스케일링
                scaled_pixmap = pixmap.scaled(width, height, 
                                            Qt.AspectRatioMode.IgnoreAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
                painter.drawPixmap(x, y, scaled_pixmap)
        
        # 윈도우 테두리 그리기
        painter.setPen(QPen(QColor(52, 73, 94), 2))
        painter.setBrush(QBrush(QColor(44, 62, 80, 100)))  # 반투명
        painter.drawRect(x, y, width, height)
        
        # 윈도우 제목 표시
        painter.setPen(QColor(236, 240, 241))
        painter.setFont(QFont("Arial", 8))
        painter.drawText(x + 5, y + 15, f"Window: {element.name}")
    
    def _render_container_window(self, painter: QPainter, element: GUIElement):
        """containerWindowType 렌더링 (HOI4 메인 컨테이너)"""
        x, y = element.position.x, element.position.y
        
        if element.size:
            width, height = element.size.width, element.size.height
        else:
            width, height = self.window_size.width, self.window_size.height
        
        # 배경 이미지가 있는 경우
        if element.sprite_type and element.sprite_type in self.gfx_data:
            pixmap = self._load_gfx_image(element.sprite_type)
            if pixmap:
                # 이미지를 컨테이너 크기에 맞게 스케일링
                scaled_pixmap = pixmap.scaled(width, height, 
                                            Qt.AspectRatioMode.IgnoreAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
                painter.drawPixmap(x, y, scaled_pixmap)
        
        # 컨테이너 테두리 그리기 (동적 요소는 다른 색상으로)
        if element.is_dynamic:
            painter.setPen(QPen(QColor(230, 126, 34), 3))  # 주황색 (동적)
            painter.setBrush(QBrush(QColor(230, 126, 34, 30)))
        else:
            painter.setPen(QPen(QColor(41, 128, 185), 3))  # 파란색 (정적)
            painter.setBrush(QBrush(QColor(52, 73, 94, 50)))
        painter.drawRect(x, y, width, height)
        
        # 컨테이너 제목 표시 (동적 정보 포함)
        painter.setPen(QColor(236, 240, 241))
        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        title = f"Container: {element.name}"
        if element.is_dynamic:
            title += " [DYNAMIC]"
        painter.drawText(x + 5, y + 20, title)
        
        # 가시성 조건 표시 (있는 경우)
        if element.visible_condition:
            painter.setPen(QColor(241, 196, 15))  # 노란색
            painter.setFont(QFont("Arial", 7))
            painter.drawText(x + 5, y + 35, f"Visible: {element.visible_condition[:30]}...")
    
    def _render_icon(self, painter: QPainter, element: GUIElement):
        """iconType 렌더링"""
        x, y = element.position.x, element.position.y
        
        if element.sprite_type and element.sprite_type in self.gfx_data:
            pixmap = self._load_gfx_image(element.sprite_type)
            if pixmap:
                painter.drawPixmap(x, y, pixmap)
                return
        
        # 기본 아이콘 (이미지를 찾을 수 없는 경우)
        size = 32
        
        # 동적 요소는 다른 색상으로 표시
        if element.is_dynamic:
            painter.setPen(QPen(QColor(230, 126, 34), 2))  # 주황색
            painter.setBrush(QBrush(QColor(230, 126, 34, 50)))
        else:
            painter.setPen(QPen(QColor(231, 76, 60), 2))  # 빨간색
            painter.setBrush(QBrush(QColor(231, 76, 60, 50)))
        painter.drawRect(x, y, size, size)
        
        # 아이콘 이름 표시
        display_name = element.name[:10]
        if element.is_dynamic:
            display_name += " [D]"
        painter.setPen(QColor(236, 240, 241))
        painter.setFont(QFont("Arial", 6))
        painter.drawText(x, y + size + 10, display_name)
        
        # 동적 요소 표시기
        if element.is_dynamic:
            self._render_dynamic_indicator(painter, element, x, y, size, size)
    
    def _render_button(self, painter: QPainter, element: GUIElement):
        """buttonType 렌더링 (HOI4 속성 지원)"""
        x, y = element.position.x, element.position.y
        width = element.size.width if element.size else 100
        height = element.size.height if element.size else 30
        
        # 위치 조정 (orientation 지원)
        if element.orientation:
            x, y = self._apply_orientation(x, y, width, height, element.orientation)
        
        if element.sprite_type and element.sprite_type in self.gfx_data:
            pixmap = self._load_gfx_image(element.sprite_type)
            if pixmap:
                scaled_pixmap = pixmap.scaled(width, height,
                                            Qt.AspectRatioMode.IgnoreAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
                painter.drawPixmap(x, y, scaled_pixmap)
        else:
            # 기본 버튼 스타일 (동적 요소는 다른 색상으로)
            if element.is_dynamic:
                painter.setPen(QPen(QColor(230, 126, 34), 2))  # 주황색 (동적)
                painter.setBrush(QBrush(QColor(230, 126, 34, 100)))
            else:
                painter.setPen(QPen(QColor(52, 152, 219), 2))  # 파란색 (정적)
                painter.setBrush(QBrush(QColor(52, 152, 219, 100)))
            painter.drawRoundedRect(x, y, width, height, 5, 5)
        
        # 버튼 텍스트 표시 (가능한 경우)
        display_text = element.button_text or element.name
        if element.is_dynamic:
            display_text += " [D]"  # 동적 표시
        painter.setPen(QColor(236, 240, 241))
        
        # 폰트 설정
        font_size = 8
        if element.button_font:
            if "24" in element.button_font:
                font_size = 12
            elif "18" in element.button_font:
                font_size = 10
            elif "20" in element.button_font:
                font_size = 11
        
        painter.setFont(QFont("Arial", font_size))
        text_rect = QRect(x, y, width, height)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, display_text)
        
        # 동적 요소의 상세 정보 표시 (작은 아이콘으로)
        if element.is_dynamic:
            self._render_dynamic_indicator(painter, element, x, y, width, height)
    
    def _render_dynamic_indicator(self, painter: QPainter, element: GUIElement, x: int, y: int, width: int, height: int):
        """동적 요소의 고급 시각적 표시기 렌더링"""
        # 기본 동적 표시기
        indicator_size = 10
        indicator_x = x + width - indicator_size - 2
        indicator_y = y + 2
        
        # 동적 타입에 따른 색상 결정
        indicator_color = QColor(230, 126, 34)  # 기본 주황색
        indicator_text = "D"
        
        # 특별한 동적 기능에 따른 표시기 변경
        if hasattr(element, 'scripted_data'):
            scripted_data = element.scripted_data
            if scripted_data.get('animation_type'):
                indicator_color = QColor(155, 89, 182)  # 보라색 (애니메이션)
                indicator_text = "A"
            elif scripted_data.get('keyframe'):
                indicator_color = QColor(52, 152, 219)  # 파란색 (키프레임)
                indicator_text = "K"
            elif scripted_data.get('input_handler'):
                indicator_color = QColor(46, 204, 113)  # 녹색 (입력 핸들러)
                indicator_text = "I"
        
        # 배경 원
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.setPen(QPen(indicator_color, 2))
        painter.drawEllipse(indicator_x, indicator_y, indicator_size, indicator_size)
        
        # 중앙에 텍스트
        painter.setPen(indicator_color)
        painter.setFont(QFont("Arial", 7, QFont.Weight.Bold))
        painter.drawText(indicator_x + 2, indicator_y + 7, indicator_text)
        
        # 추가 정보 표시 (작은 텍스트로)
        if element.visible_condition or element.click_effect:
            info_y = y + height + 2
            painter.setPen(QColor(241, 196, 15))  # 노란색
            painter.setFont(QFont("Arial", 6))
            
            info_text = ""
            if element.visible_condition:
                info_text += f"Visible: {element.visible_condition[:20]}..."
            if element.click_effect:
                if info_text:
                    info_text += " | "
                info_text += f"Click: {element.click_effect[:20]}..."
            
            if info_text:
                painter.drawText(x, info_y, info_text)
    
    def _render_advanced_dynamic_info(self, painter: QPainter, element: GUIElement, x: int, y: int):
        """고급 동적 정보 렌더링 (디버그 모드용)"""
        if not hasattr(element, 'scripted_data') or not element.scripted_data:
            return
            
        scripted_data = element.scripted_data
        info_lines = []
        
        # 애니메이션 정보
        if scripted_data.get('animation_type'):
            info_lines.append(f"Anim: {scripted_data['animation_type']}")
            if scripted_data.get('animation_time'):
                info_lines[-1] += f" ({scripted_data['animation_time']}s)"
        
        # 사운드 정보
        if scripted_data.get('upsound'):
            info_lines.append(f"Sound: {scripted_data['upsound']}")
        
        # 입력 핸들러
        if scripted_data.get('input_handler'):
            handlers = list(scripted_data['input_handler'].keys())[:2]  # 최대 2개만
            info_lines.append(f"Input: {', '.join(handlers)}")
        
        # 스코프 조건
        if scripted_data.get('scope_conditions'):
            scopes = list(scripted_data['scope_conditions'].keys())[:2]
            info_lines.append(f"Scope: {', '.join(scopes)}")
        
        # 정보 표시
        if info_lines:
            painter.setPen(QColor(149, 165, 166))
            painter.setFont(QFont("Arial", 6))
            
            for i, line in enumerate(info_lines[:3]):  # 최대 3줄
                painter.drawText(x, y - 10 - (i * 8), line)
    
    def _render_text_box(self, painter: QPainter, element: GUIElement):
        """instantTextBoxType 렌더링 (HOI4 속성 지원)"""
        x, y = element.position.x, element.position.y
        
        # 위치 조정 (orientation 지원)
        width = element.max_width or 200
        height = element.max_height or 20
        
        if element.orientation:
            x, y = self._apply_orientation(x, y, width, height, element.orientation)
        
        # 폰트 설정
        font_size = 12
        if element.font:
            if "24" in element.font:
                font_size = 16
            elif "20" in element.font:
                font_size = 14
            elif "18" in element.font:
                font_size = 12
            elif "16" in element.font:
                font_size = 11
            elif "14" in element.font:
                font_size = 10
        
        font = QFont("Arial", font_size)
        if element.font and "b" in element.font.lower():
            font.setBold(True)
        
        painter.setFont(font)
        
        # 텍스트 그리기
        text = element.text or element.name
        if element.is_dynamic:
            text += " [D]"
            
        text_rect = QRect(x, y, width, height)
        
        # 정렬 설정
        alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        if element.format_align:
            if "center" in element.format_align.lower() or "centre" in element.format_align.lower():
                alignment = Qt.AlignmentFlag.AlignCenter
            elif "right" in element.format_align.lower():
                alignment = Qt.AlignmentFlag.AlignRight
        
        # 동적 요소는 다른 색상으로 텍스트 표시
        if element.is_dynamic:
            painter.setPen(QColor(230, 126, 34))  # 주황색
        else:
            painter.setPen(QColor(44, 62, 80))  # 기본 어두운 색
            
        painter.drawText(text_rect, alignment, text)
        
        # 텍스트 박스 경계 표시 (동적 요소는 다른 색상)
        if element.is_dynamic:
            painter.setPen(QPen(QColor(230, 126, 34, 150), 1, Qt.PenStyle.DashLine))
        else:
            painter.setPen(QPen(QColor(155, 89, 182, 100), 1, Qt.PenStyle.DashLine))
        painter.drawRect(text_rect)
        
        # 동적 요소 표시기
        if element.is_dynamic:
            self._render_dynamic_indicator(painter, element, x, y, width, height)
    
    def _render_checkbox(self, painter: QPainter, element: GUIElement):
        """checkboxType 렌더링"""
        x, y = element.position.x, element.position.y
        size = 24
        
        if element.sprite_type and element.sprite_type in self.gfx_data:
            pixmap = self._load_gfx_image(element.sprite_type)
            if pixmap:
                scaled_pixmap = pixmap.scaled(size, size,
                                            Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
                painter.drawPixmap(x, y, scaled_pixmap)
                return
        
        # 기본 체크박스 스타일
        painter.setPen(QPen(QColor(52, 152, 219), 2))
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawRoundedRect(x, y, size, size, 4, 4)
        
        # 체크 표시
        painter.setPen(QPen(QColor(52, 152, 219), 3))
        check_offset = 6
        painter.drawLine(x + check_offset, y + size//2, 
                        x + size//2, y + size - check_offset)
        painter.drawLine(x + size//2, y + size - check_offset,
                        x + size - check_offset, y + check_offset)
        
        # 체크박스 이름 표시
        painter.setPen(QColor(236, 240, 241))
        painter.setFont(QFont("Arial", 8))
        painter.drawText(x + size + 5, y + size//2 + 3, element.name)
    
    def _render_scrollbar(self, painter: QPainter, element: GUIElement):
        """scrollbarType 렌더링"""
        x, y = element.position.x, element.position.y
        width = element.size.width if element.size else 20
        height = element.size.height if element.size else 200
        
        # 스크롤바 배경
        painter.setPen(QPen(QColor(189, 195, 199), 1))
        painter.setBrush(QBrush(QColor(236, 240, 241)))
        painter.drawRect(x, y, width, height)
        
        # 스크롤 핸들
        handle_height = max(30, height // 4)
        handle_y = y + height // 3
        painter.setPen(QPen(QColor(52, 152, 219), 2))
        painter.setBrush(QBrush(QColor(52, 152, 219, 150)))
        painter.drawRoundedRect(x + 2, handle_y, width - 4, handle_height, 3, 3)
        
        # 스크롤바 이름 표시
        painter.setPen(QColor(236, 240, 241))
        painter.setFont(QFont("Arial", 6))
        painter.save()
        painter.translate(x + width + 5, y + height//2)
        painter.rotate(90)
        painter.drawText(0, 0, element.name[:8])
        painter.restore()
    
    def _render_gridbox(self, painter: QPainter, element: GUIElement):
        """gridBoxType 렌더링"""
        x, y = element.position.x, element.position.y
        width = element.size.width if element.size else 300
        height = element.size.height if element.size else 200
        
        # 그리드박스 배경
        painter.setPen(QPen(QColor(149, 165, 166), 2))
        painter.setBrush(QBrush(QColor(236, 240, 241, 100)))
        painter.drawRoundedRect(x, y, width, height, 5, 5)
        
        # 그리드 라인
        painter.setPen(QPen(QColor(189, 195, 199), 1, Qt.PenStyle.DashLine))
        cell_width = width // 4
        cell_height = height // 3
        
        # 수직 라인
        for i in range(1, 4):
            line_x = x + i * cell_width
            painter.drawLine(line_x, y, line_x, y + height)
        
        # 수평 라인
        for i in range(1, 3):
            line_y = y + i * cell_height
            painter.drawLine(x, line_y, x + width, line_y)
        
        # 그리드박스 제목 표시
        painter.setPen(QColor(44, 62, 80))
        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        painter.drawText(x + 5, y + 15, f"Grid: {element.name}")
    
    def _render_listbox(self, painter: QPainter, element: GUIElement):
        """listboxType 렌더링"""
        x, y = element.position.x, element.position.y
        width = element.size.width if element.size else 200
        height = element.size.height if element.size else 100
        
        # 리스트박스 배경
        painter.setPen(QPen(QColor(127, 140, 141), 2))
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawRect(x, y, width, height)
        
        # 리스트 항목들 (예시)
        painter.setPen(QColor(44, 62, 80))
        painter.setFont(QFont("Arial", 8))
        item_height = 16
        for i in range(min(5, height // item_height)):
            item_y = y + 5 + i * item_height
            painter.drawText(x + 5, item_y + 12, f"Item {i + 1}")
            if i > 0:
                painter.setPen(QPen(QColor(189, 195, 199), 1))
                painter.drawLine(x + 2, item_y, x + width - 2, item_y)
                painter.setPen(QColor(44, 62, 80))
        
        # 스크롤바 표시
        if height > 80:
            scroll_x = x + width - 15
            painter.setPen(QPen(QColor(189, 195, 199), 1))
            painter.setBrush(QBrush(QColor(236, 240, 241)))
            painter.drawRect(scroll_x, y, 15, height)
            
            # 스크롤 핸들
            handle_height = height // 3
            painter.setPen(QPen(QColor(127, 140, 141), 1))
            painter.setBrush(QBrush(QColor(189, 195, 199)))
            painter.drawRect(scroll_x + 2, y + height // 4, 11, handle_height)
        
        # 리스트박스 이름 표시
        painter.setPen(QColor(236, 240, 241))
        painter.setFont(QFont("Arial", 6))
        painter.drawText(x, y - 8, element.name)
    
    def _render_editbox(self, painter: QPainter, element: GUIElement):
        """editboxType 렌더링"""
        x, y = element.position.x, element.position.y
        width = element.size.width if element.size else 150
        height = element.size.height if element.size else 25
        
        # 에디트박스 배경
        painter.setPen(QPen(QColor(127, 140, 141), 2))
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawRect(x, y, width, height)
        
        # 텍스트 내용
        painter.setPen(QColor(44, 62, 80))
        painter.setFont(QFont("Arial", 9))
        text = element.text or "Enter text..."
        text_rect = QRect(x + 5, y, width - 10, height)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, text)
        
        # 커서 표시 (점선)
        painter.setPen(QPen(QColor(52, 152, 219), 1, Qt.PenStyle.DashLine))
        cursor_x = x + 8 + painter.fontMetrics().horizontalAdvance(text[:5])
        painter.drawLine(cursor_x, y + 3, cursor_x, y + height - 3)
        
        # 에디트박스 이름 표시
        painter.setPen(QColor(236, 240, 241))
        painter.setFont(QFont("Arial", 6))
        painter.drawText(x, y - 8, element.name)
    
    def _apply_orientation(self, x: int, y: int, width: int, height: int, orientation: str) -> Tuple[int, int]:
        """HOI4 orientation 속성 적용"""
        canvas_width = self.window_size.width
        canvas_height = self.window_size.height
        
        # orientation에 따른 위치 조정
        if orientation.lower() == "center":
            x = (canvas_width - width) // 2 + x
            y = (canvas_height - height) // 2 + y
        elif orientation.lower() == "center_up":
            x = (canvas_width - width) // 2 + x
            # y는 그대로 (상단 기준)
        elif orientation.lower() == "center_down":
            x = (canvas_width - width) // 2 + x
            y = canvas_height - height + y
        elif orientation.lower() == "left_up":
            # x, y 그대로 (좌상단 기준)
            pass
        elif orientation.lower() == "right_up":
            x = canvas_width - width + x
            # y는 그대로
        elif orientation.lower() == "left_down":
            y = canvas_height - height + y
            # x는 그대로
        elif orientation.lower() == "right_down":
            x = canvas_width - width + x
            y = canvas_height - height + y
        
        return x, y
    
    def _load_gfx_image(self, sprite_type: str) -> Optional[QPixmap]:
        """GFX 이미지 로드"""
        if sprite_type not in self.gfx_data:
            return None
        
        try:
            image_path = self.gfx_data[sprite_type]
            if isinstance(image_path, dict):
                image_path = image_path.get('texturefile', '')
            
            if not os.path.exists(image_path):
                return None
            
            # DDS 파일인 경우 PIL로 변환
            if image_path.lower().endswith('.dds'):
                with Image.open(image_path) as img:
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # 임시 PNG 파일로 저장
                    temp_path = "temp_gui_preview.png"
                    img.save(temp_path, "PNG")
                    pixmap = QPixmap(temp_path)
                    
                    # 임시 파일 삭제
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    
                    return pixmap
            else:
                return QPixmap(image_path)
                
        except Exception as e:
            print(f"이미지 로드 오류 ({sprite_type}): {e}")
            return None
    
    def show_context_menu(self, position):
        """컨텍스트 메뉴 표시"""
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QAction
        
        menu = QMenu(self)
        
        # 새로고침 액션
        refresh_action = QAction("새로고침", self)
        refresh_action.triggered.connect(self.refresh_canvas)
        menu.addAction(refresh_action)
        
        # 줌 액션
        menu.addSeparator()
        zoom_in_action = QAction("확대", self)
        zoom_in_action.triggered.connect(self.zoom_in)
        menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction("축소", self)
        zoom_out_action.triggered.connect(self.zoom_out)
        menu.addAction(zoom_out_action)
        
        zoom_reset_action = QAction("원본 크기", self)
        zoom_reset_action.triggered.connect(self.zoom_reset)
        menu.addAction(zoom_reset_action)
        
        # 내보내기 액션
        menu.addSeparator()
        export_action = QAction("이미지로 저장", self)
        export_action.triggered.connect(self.export_as_image)
        menu.addAction(export_action)
        
        # 디버그 정보 액션
        debug_action = QAction("디버그 정보", self)
        debug_action.triggered.connect(self.show_debug_info)
        menu.addAction(debug_action)
        
        menu.exec(self.mapToGlobal(position))
    
    def refresh_canvas(self):
        """캔버스 새로고침"""
        self.update()
    
    def zoom_in(self):
        """확대"""
        self.scale_factor = min(self.scale_factor * 1.2, 3.0)
        self.update()
    
    def zoom_out(self):
        """축소"""
        self.scale_factor = max(self.scale_factor / 1.2, 0.2)
        self.update()
    
    def zoom_reset(self):
        """줌 리셋"""
        self.calculate_scale_factor()
        self.update()
    
    def export_as_image(self):
        """이미지로 내보내기"""
        from PyQt6.QtWidgets import QFileDialog
        from PyQt6.QtGui import QPainter
        
        # 기본 저장 경로 설정
        default_path = os.path.expanduser("~/Documents/gui_preview.png")
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "이미지 저장", default_path, 
            "PNG 파일 (*.png);;JPEG 파일 (*.jpg);;모든 파일 (*)"
        )
        
        if file_path:
            pixmap = QPixmap(self.size())
            pixmap.fill(QColor(44, 62, 80))
            
            painter = QPainter(pixmap)
            self.render(painter)
            painter.end()
            
            if pixmap.save(file_path):
                print(f"이미지가 저장되었습니다: {file_path}")
            else:
                print("이미지 저장에 실패했습니다.")
    
    def show_debug_info(self):
        """디버그 정보 표시"""
        from PyQt6.QtWidgets import QMessageBox
        
        info = f"""GUI 프리뷰 디버그 정보
        
요소 개수: {len(self.elements)}
윈도우 크기: {self.window_size.width} x {self.window_size.height}
스케일 팩터: {self.scale_factor:.2f}
캔버스 크기: {self.width()} x {self.height()}
GFX 데이터: {len(self.gfx_data)}개 항목

요소 유형 분포:"""
        
        element_types = {}
        for element in self.elements:
            element_types[element.element_type] = element_types.get(element.element_type, 0) + 1
        
        for element_type, count in element_types.items():
            info += f"\n- {element_type}: {count}개"
        
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("디버그 정보")
        msg.setText(info)
        msg.exec()


class GUIElementTreeWidget(QTreeWidget):
    """GUI 요소들을 트리 형태로 보여주는 위젯"""
    
    def __init__(self):
        super().__init__()
        self.setHeaderLabels(["요소", "타입", "위치", "크기", "스프라이트"])
        self.setStyleSheet("""
            QTreeWidget {
                background-color: white;
                border: 1px solid gray;
            }
            QTreeWidget::item {
                padding: 4px;
            }
            QTreeWidget::item:selected {
                background-color: #316AC5;
                color: white;
            }
        """)
    
    def set_elements(self, elements: List[GUIElement]):
        """요소 목록 설정"""
        self.clear()
        
        for element in elements:
            item = QTreeWidgetItem()
            item.setText(0, element.name)
            item.setText(1, element.element_type)
            item.setText(2, f"({element.position.x}, {element.position.y})")
            
            if element.size:
                item.setText(3, f"{element.size.width}x{element.size.height}")
            else:
                item.setText(3, "-")
            
            item.setText(4, element.sprite_type or "-")
            
            # 타입별 색상 구분
            if element.element_type == 'containerWindowType':
                item.setBackground(0, QColor(220, 237, 255))  # 더 진한 파란색 (메인 컨테이너)
            elif element.element_type == 'windowType':
                item.setBackground(0, QColor(230, 247, 255))
            elif element.element_type == 'iconType':
                item.setBackground(0, QColor(255, 245, 230))
            elif element.element_type == 'buttonType':
                item.setBackground(0, QColor(230, 255, 230))
            elif element.element_type == 'instantTextBoxType':
                item.setBackground(0, QColor(255, 230, 255))
            elif element.element_type == 'listboxType':
                item.setBackground(0, QColor(245, 245, 220))
            elif element.element_type == 'editboxType':
                item.setBackground(0, QColor(240, 255, 240))
            
            self.addTopLevelItem(item)
        
        # 컬럼 너비 자동 조정
        for i in range(5):
            self.resizeColumnToContents(i)


class GUIPreviewWidget(QWidget):
    """GUI 미리보기 통합 위젯"""
    
    def __init__(self, gfx_data: Dict[str, str] = None, mod_folder_path: str = None):
        super().__init__()
        self.parser = HOI4GUIParser()
        self.scripted_gui_parser = ScriptedGUIParser()
        self.gfx_data = gfx_data or {}
        self.mod_folder_path = mod_folder_path
        self.current_file_path = None
        self.current_scripted_gui_path = None
        self.init_ui()
    
    def init_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 상단 컨트롤
        control_widget = QWidget()
        control_widget.setMaximumHeight(50)  # 높이 제한
        control_layout = QHBoxLayout()
        control_layout.setContentsMargins(5, 5, 5, 5)  # 여백 줄이기
        control_widget.setLayout(control_layout)
        
        self.load_btn = QPushButton("GUI 파일 로드")
        self.load_btn.setMaximumWidth(120)  # 버튼 너비 제한
        self.load_btn.setMaximumHeight(35)  # 버튼 높이 제한
        self.load_btn.clicked.connect(self.load_gui_file)
        
        self.load_scripted_btn = QPushButton("Scripted GUI 로드")
        self.load_scripted_btn.setMaximumWidth(140)  # 버튼 너비 제한
        self.load_scripted_btn.setMaximumHeight(35)  # 버튼 높이 제한
        self.load_scripted_btn.clicked.connect(self.load_scripted_gui_file)
        
        self.file_label = QLabel("파일을 선택하세요")
        
        control_layout.addWidget(self.load_btn)
        control_layout.addWidget(self.load_scripted_btn)
        control_layout.addWidget(self.file_label)
        control_layout.addStretch()
        
        layout.addWidget(control_widget)
        
        # 메인 영역 분할
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(main_splitter)
        
        # 좌측: 미리보기 캔버스
        self.canvas = GUIPreviewCanvas(self.gfx_data)
        main_splitter.addWidget(self.canvas)
        
        # 우측: 요소 트리와 정보
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_widget.setLayout(right_layout)
        
        # 요소 트리
        tree_label = QLabel("GUI 요소 목록")
        right_layout.addWidget(tree_label)
        
        self.element_tree = GUIElementTreeWidget()
        right_layout.addWidget(self.element_tree)
        
        # 파일 내용 표시
        content_label = QLabel("파일 내용")
        right_layout.addWidget(content_label)
        
        self.content_text = QTextEdit()
        self.content_text.setReadOnly(True)
        self.content_text.setMaximumHeight(200)
        right_layout.addWidget(self.content_text)
        
        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([600, 400])
    
    def set_gfx_data(self, gfx_data: Dict[str, str]):
        """GFX 데이터 설정"""
        self.gfx_data = gfx_data
        self.canvas.gfx_data = gfx_data
        if self.current_file_path:
            self.load_gui_file(self.current_file_path)
    
    def load_gui_file(self, file_path: str = None):
        """GUI 파일 로드"""
        if not file_path:
            # 기본 시작 경로 설정 (모드 폴더 우선, 없으면 HOI4 interface 폴더)
            default_path = self.mod_folder_path if self.mod_folder_path else os.path.expanduser(r"~\Documents\Paradox Interactive\Hearts of Iron IV\mod")
            if not os.path.exists(default_path):
                default_path = os.path.expanduser("~/Documents")
            
            file_path, _ = QFileDialog.getOpenFileName(
                self, "GUI 파일 선택", default_path, "GUI 파일 (*.gui);;모든 파일 (*)"
            )
        
        if not file_path:
            return
        
        self.current_file_path = file_path
        # 상대 경로로 표시
        if self.mod_folder_path and file_path.startswith(self.mod_folder_path):
            display_path = os.path.relpath(file_path, self.mod_folder_path)
        else:
            display_path = os.path.basename(file_path)
        self.file_label.setText(display_path)
        
        # 파일 파싱
        elements = self.parser.parse_file(file_path)
        
        if not elements:
            error_details = ""
            if hasattr(self.parser, 'parse_errors') and self.parser.parse_errors:
                error_details = f"\n오류 상세:\n" + "\n".join(self.parser.parse_errors[:3])
            
            display_path = os.path.relpath(file_path, self.mod_folder_path) if self.mod_folder_path and file_path.startswith(self.mod_folder_path) else os.path.basename(file_path)
            self.file_label.setText(f"파싱 실패: {display_path}")
            
            # 오류 메시지 다이얼로그 표시
            from PyQt6.QtWidgets import QMessageBox
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("GUI 파일 파싱 오류")
            msg.setText(f"파일을 파싱할 수 없습니다: {display_path}")
            msg.setDetailedText(error_details if error_details else "알 수 없는 오류가 발생했습니다.")
            msg.exec()
            return
        
        # 캔버스에 요소 설정
        self.canvas.set_elements(elements, self.parser.window_size)
        
        # 트리에 요소 설정
        self.element_tree.set_elements(elements)
        
        # 파일 내용 표시
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
            self.content_text.setText(content[:2000] + "..." if len(content) > 2000 else content)
        except Exception as e:
            self.content_text.setText(f"파일 읽기 오류: {e}")
    
    def load_scripted_gui_file(self, file_path: str = None):
        """Scripted GUI 파일 로드"""
        if not file_path:
            # 기본 시작 경로 설정
            default_path = self.mod_folder_path if self.mod_folder_path else os.path.expanduser(r"~\Documents\Paradox Interactive\Hearts of Iron IV\mod")
            if not os.path.exists(default_path):
                default_path = os.path.expanduser("~/Documents")
            
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Scripted GUI 파일 선택", default_path, "Scripted GUI 파일 (*.txt);;모든 파일 (*)"
            )
        
        if not file_path:
            return
        
        self.current_scripted_gui_path = file_path
        
        # Scripted GUI 파일 파싱
        scripted_gui_definitions = self.scripted_gui_parser.parse_file(file_path)
        
        if not scripted_gui_definitions:
            from PyQt6.QtWidgets import QMessageBox
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("Scripted GUI 파일 파싱 오류")
            display_path = os.path.relpath(file_path, self.mod_folder_path) if self.mod_folder_path and file_path.startswith(self.mod_folder_path) else os.path.basename(file_path)
            msg.setText(f"Scripted GUI 파일을 파싱할 수 없습니다: {display_path}")
            msg.exec()
            return
        
        # Parser에 scripted GUI 데이터 설정
        self.parser.set_scripted_gui_data(scripted_gui_definitions)
        
        # 파일 레이블 업데이트 (상대 경로로 표시)
        gui_display = "없음"
        if self.current_file_path:
            gui_display = os.path.relpath(self.current_file_path, self.mod_folder_path) if self.mod_folder_path and self.current_file_path.startswith(self.mod_folder_path) else os.path.basename(self.current_file_path)
        
        scripted_display = os.path.relpath(file_path, self.mod_folder_path) if self.mod_folder_path and file_path.startswith(self.mod_folder_path) else os.path.basename(file_path)
        self.file_label.setText(f"GUI: {gui_display} | Scripted: {scripted_display}")
        
        # 기존 GUI 파일이 로드되어 있으면 다시 파싱
        if self.current_file_path:
            self.load_gui_file(self.current_file_path)
        
        display_path = os.path.relpath(file_path, self.mod_folder_path) if self.mod_folder_path and file_path.startswith(self.mod_folder_path) else os.path.basename(file_path)
        print(f"Loaded {len(scripted_gui_definitions)} scripted GUI definitions from {display_path}")


class GUIPreviewWindow(QMainWindow):
    """독립 실행용 GUI 미리보기 윈도우"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HOI4 GUI 미리보기 도구")
        self.setGeometry(100, 100, 1200, 800)
        
        # 메인 위젯 설정
        self.preview_widget = GUIPreviewWidget()
        self.setCentralWidget(self.preview_widget)
        
        # 메뉴바 설정
        self.create_menus()
        
        # 기본 스타일
    
    def create_menus(self):
        """메뉴바 생성"""
        menubar = self.menuBar()
        
        # 파일 메뉴
        file_menu = menubar.addMenu('파일')
        
        open_action = file_menu.addAction('GUI 파일 열기')
        open_action.triggered.connect(self.preview_widget.load_gui_file)
        
        file_menu.addSeparator()
        
        exit_action = file_menu.addAction('종료')
        exit_action.triggered.connect(self.close)


def main():
    """독립 실행 예시"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # 테스트용 GFX 데이터 (실제로는 GFX 매니저에서 가져옴)
    test_gfx_data = {
        'GFX_tiled_window_transparent': 'test_background.png',
        'GFX_idea_generic_agrarian_society': 'test_icon.png',
    }
    
    window = GUIPreviewWindow()
    window.preview_widget.set_gfx_data(test_gfx_data)
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()