#!/usr/bin/env python3
"""
Utility functions for Claude Agent SDK scripts.

This module provides common utilities for formatting and displaying
messages from the Claude Agent SDK.
"""

import json
import textwrap
from typing import Any


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'


def truncate_text(text: str, max_length: int = 200) -> str:
    """Truncate text to max_length and add ellipsis if needed."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def format_json_compact(data: Any, max_length: int = 300) -> str:
    """Format JSON data compactly for display."""
    try:
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        if len(json_str) > max_length:
            return json_str[:max_length] + "\n    ..."
        return json_str
    except (TypeError, ValueError):
        return str(data)[:max_length]


class MessageFormatter:
    """
    Formatter for Claude Agent SDK messages.

    Handles all message types:
    - UserMessage: User input
    - AssistantMessage: Contains TextBlock, ThinkingBlock, ToolUseBlock, ToolResultBlock
    - SystemMessage: System events
    - ResultMessage: Final result with cost/usage info
    """

    def __init__(self, indent: str = "    ", use_colors: bool = True):
        """
        Initialize the formatter.

        Args:
            indent: Indentation string for nested output
            use_colors: Whether to use ANSI color codes
        """
        self.indent = indent
        self.use_colors = use_colors
        self._sdk_types_loaded = False
        self._types = {}

    def _load_sdk_types(self) -> bool:
        """Lazy load SDK types to avoid import errors if SDK not installed."""
        if self._sdk_types_loaded:
            return bool(self._types)

        self._sdk_types_loaded = True
        try:
            from claude_agent_sdk import (
                UserMessage,
                AssistantMessage,
                SystemMessage,
                ResultMessage,
            )
            from claude_agent_sdk.types import (
                TextBlock,
                ThinkingBlock,
                ToolUseBlock,
                ToolResultBlock,
            )
            self._types = {
                'UserMessage': UserMessage,
                'AssistantMessage': AssistantMessage,
                'SystemMessage': SystemMessage,
                'ResultMessage': ResultMessage,
                'TextBlock': TextBlock,
                'ThinkingBlock': ThinkingBlock,
                'ToolUseBlock': ToolUseBlock,
                'ToolResultBlock': ToolResultBlock,
            }
            return True
        except ImportError:
            return False

    def _color(self, color_code: str) -> str:
        """Return color code if colors are enabled, empty string otherwise."""
        return color_code if self.use_colors else ""

    def format(self, message: Any) -> str:
        """
        Format a message from the Claude Agent SDK.

        Args:
            message: A message object from the SDK

        Returns:
            Formatted string representation of the message
        """
        lines = []
        indent = self.indent

        if not self._load_sdk_types():
            # Fallback if SDK not available
            lines.append(f"{indent}{self._color(Colors.DIM)}[Message]{self._color(Colors.ENDC)} {str(message)[:200]}")
            return "\n".join(lines)

        types = self._types

        # Handle UserMessage
        if isinstance(message, types['UserMessage']):
            content = message.content if isinstance(message.content, str) else str(message.content)
            lines.append(f"{indent}{self._color(Colors.BLUE)}[User]{self._color(Colors.ENDC)} {truncate_text(content, 100)}")
            return "\n".join(lines)

        # Handle AssistantMessage
        if isinstance(message, types['AssistantMessage']):
            lines.append(f"{indent}{self._color(Colors.GREEN)}[Assistant]{self._color(Colors.ENDC)} (model: {message.model})")
            for block in message.content:
                lines.extend(self._format_content_block(block))
            return "\n".join(lines)

        # Handle SystemMessage
        if isinstance(message, types['SystemMessage']):
            subtype = message.subtype
            data_preview = format_json_compact(message.data, 150) if message.data else ""
            lines.append(f"{indent}{self._color(Colors.YELLOW)}[System:{subtype}]{self._color(Colors.ENDC)} {data_preview}")
            return "\n".join(lines)

        # Handle ResultMessage
        if isinstance(message, types['ResultMessage']):
            lines.extend(self._format_result_message(message))
            return "\n".join(lines)

        # Fallback for unknown message types
        lines.append(f"{indent}{self._color(Colors.DIM)}[Unknown]{self._color(Colors.ENDC)} {type(message).__name__}: {str(message)[:150]}")
        return "\n".join(lines)

    def _format_content_block(self, block: Any) -> list[str]:
        """Format a content block from an AssistantMessage."""
        lines = []
        indent = self.indent
        types = self._types

        if isinstance(block, types['TextBlock']):
            text = block.text.strip()
            if text:
                lines.append(f"{indent}  {self._color(Colors.CYAN)}[Text]{self._color(Colors.ENDC)}")
                wrapped = textwrap.fill(
                    text, width=80,
                    initial_indent=indent + "    ",
                    subsequent_indent=indent + "    "
                )
                if len(wrapped) > 500:
                    wrapped = wrapped[:500] + "..."
                lines.append(wrapped)

        elif isinstance(block, types['ThinkingBlock']):
            thinking = truncate_text(block.thinking, 150)
            lines.append(f"{indent}  {self._color(Colors.YELLOW)}[Thinking]{self._color(Colors.ENDC)} {thinking}")

        elif isinstance(block, types['ToolUseBlock']):
            lines.append(f"{indent}  {self._color(Colors.HEADER)}[Tool Use]{self._color(Colors.ENDC)} {self._color(Colors.BOLD)}{block.name}{self._color(Colors.ENDC)}")
            lines.append(f"{indent}    ID: {block.id}")
            tool_input = format_json_compact(block.input, 200)
            for line in tool_input.split('\n'):
                lines.append(f"{indent}    {line}")

        elif isinstance(block, types['ToolResultBlock']):
            is_error = block.is_error if block.is_error else False
            if is_error:
                status = f"{self._color(Colors.RED)}ERROR{self._color(Colors.ENDC)}"
            else:
                status = f"{self._color(Colors.GREEN)}OK{self._color(Colors.ENDC)}"
            lines.append(f"{indent}  {self._color(Colors.HEADER)}[Tool Result]{self._color(Colors.ENDC)} [{status}]")
            lines.append(f"{indent}    Tool Use ID: {block.tool_use_id}")
            if block.content:
                content_str = str(block.content) if not isinstance(block.content, str) else block.content
                content_preview = truncate_text(content_str, 300)
                content_lines = content_preview.split('\n')[:5]
                for line in content_lines:
                    lines.append(f"{indent}    {line}")
                if len(content_preview.split('\n')) > 5:
                    lines.append(f"{indent}    ...")

        else:
            lines.append(f"{indent}  {self._color(Colors.DIM)}[Block]{self._color(Colors.ENDC)} {type(block).__name__}: {str(block)[:100]}")

        return lines

    def _format_result_message(self, message: Any) -> list[str]:
        """Format a ResultMessage."""
        lines = []
        indent = self.indent

        if message.is_error:
            status = f"{self._color(Colors.RED)}ERROR{self._color(Colors.ENDC)}"
        else:
            status = f"{self._color(Colors.GREEN)}SUCCESS{self._color(Colors.ENDC)}"

        lines.append(f"{indent}{self._color(Colors.BOLD)}[Result]{self._color(Colors.ENDC)} [{status}]")
        lines.append(f"{indent}  Session ID: {message.session_id}")
        lines.append(f"{indent}  Duration: {message.duration_ms}ms (API: {message.duration_api_ms}ms)")
        lines.append(f"{indent}  Turns: {message.num_turns}")

        if message.total_cost_usd is not None:
            lines.append(f"{indent}  Cost: ${message.total_cost_usd:.6f}")

        if message.usage:
            usage_str = format_json_compact(message.usage, 200)
            lines.append(f"{indent}  Usage: {usage_str}")

        if message.result:
            result_preview = truncate_text(message.result, 300)
            lines.append(f"{indent}  Result: {result_preview}")

        return lines

    def print(self, message: Any) -> None:
        """Format and print a message."""
        print(self.format(message))


# Default formatter instance for convenience
_default_formatter = MessageFormatter()


def format_message(message: Any) -> str:
    """
    Format a message from the Claude Agent SDK.

    Args:
        message: A message object from the SDK

    Returns:
        Formatted string representation of the message
    """
    return _default_formatter.format(message)


def print_message(message: Any) -> None:
    """
    Format and print a message from the Claude Agent SDK.

    Args:
        message: A message object from the SDK
    """
    _default_formatter.print(message)
