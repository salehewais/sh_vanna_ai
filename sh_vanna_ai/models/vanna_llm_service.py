"""
Custom LLM Service for Vanna 2.0 that integrates with local llama.cpp server
"""
import logging
import asyncio
import requests
from typing import Optional, List, Dict, Any, AsyncIterator
from vanna.core.llm import LlmService
from vanna.core.llm.base import LlmStreamChunk

_logger = logging.getLogger(__name__)


class LocalLlamaCppLlmService(LlmService):
    """LLM Service adapter for local llama.cpp server"""
    
    def __init__(self, llm_url: str = "http://localhost:8080/completion", temperature: float = 0.1, max_tokens: int = 500):
        """
        Initialize the local LLM service
        
        Args:
            llm_url: URL to the llama.cpp server completion endpoint
            temperature: Temperature for LLM generation
            max_tokens: Maximum tokens to generate
        """
        # Initialize parent class without arguments
        super().__init__()
        
        self.llm_url = llm_url
        self.temperature = temperature
        self.max_tokens = max_tokens
    
    def generate_response(
        self,
        messages,
        system: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Generate a response from the local LLM
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            system: Optional system message
            **kwargs: Additional parameters
            
        Returns:
            Generated response text
        """
        response = self.send_request(messages, system, **kwargs)
        return response.get('content', '')
    
    def _messages_to_prompt(self, messages, system: Optional[str] = None) -> str:
        """
        Convert messages to a prompt format for llama.cpp
        
        Args:
            messages: List of message dicts or tuples (role, content)
            system: Optional system message
            
        Returns:
            Formatted prompt string
        """
        prompt_parts = []
        
        if system:
            prompt_parts.append(f"System: {system}\n")
        
        for msg in messages:
            # Handle both dict and tuple formats
            if isinstance(msg, dict):
                role = msg.get('role', 'user')
                content = msg.get('content', '')
            elif isinstance(msg, tuple) and len(msg) >= 2:
                # Tuple format: (role, content) or (role, content, ...)
                role = msg[0]
                content = msg[1]
            elif isinstance(msg, tuple) and len(msg) == 1:
                # Single element tuple, treat as content
                role = 'user'
                content = msg[0]
            else:
                # Fallback: treat as string content
                role = 'user'
                content = str(msg)
            
            if role == 'system':
                prompt_parts.append(f"System: {content}\n")
            elif role == 'user':
                prompt_parts.append(f"Human: {content}\n")
            elif role == 'assistant':
                prompt_parts.append(f"Assistant: {content}\n")
            else:
                # Unknown role, default to user
                prompt_parts.append(f"Human: {content}\n")
        
        prompt_parts.append("Assistant:")
        
        return '\n'.join(prompt_parts)
    
    def generate_sql(self, question: str, **kwargs) -> str:
        """
        Generate SQL from a question (for backward compatibility)
        
        Args:
            question: Natural language question
            **kwargs: Additional parameters
            
        Returns:
            Generated SQL query
        """
        messages = [
            {
                'role': 'user',
                'content': question
            }
        ]
        
        system = kwargs.get('system', 'You are a SQL expert. Generate PostgreSQL SELECT queries only.')
        
        return self.generate_response(messages, system=system, **kwargs)
    
    def send_request(
        self,
        messages,
        system: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send a request to the LLM and return the response
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            system: Optional system message
            **kwargs: Additional parameters
            
        Returns:
            Response dictionary
        """
        try:
            # Convert messages to a prompt format for llama.cpp
            prompt = self._messages_to_prompt(messages, system)
            
            # Call llama.cpp server
            response = requests.post(
                self.llm_url,
                json={
                    'prompt': prompt,
                    'temperature': kwargs.get('temperature', self.temperature),
                    'max_tokens': kwargs.get('max_tokens', self.max_tokens),
                    'stop': kwargs.get('stop', ['\n\n', 'Human:', 'Assistant:']),
                },
                timeout=kwargs.get('timeout', 30)
            )
            response.raise_for_status()
            
            data = response.json()
            content = data.get('content', '')
            
            # Clean up the response
            if isinstance(content, list):
                content = ''.join(content)
            
            return {
                'content': content.strip(),
                'raw': data
            }
            
        except Exception as e:
            _logger.error(f'LLM service error: {str(e)}')
            raise
    
    async def stream_request(
        self,
        messages,
        system: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[LlmStreamChunk]:
        """
        Stream a request to the LLM and yield response chunks as async generator
        
        Args:
            messages: List of message dicts or tuples with 'role' and 'content'
            system: Optional system message
            **kwargs: Additional parameters
            
        Yields:
            LlmStreamChunk objects with content
        """
        # For llama.cpp, we'll use the non-streaming endpoint
        # and yield the complete response as chunks
        # In a full implementation, you could use SSE or streaming endpoints
        try:
            # Run the blocking send_request in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.send_request(messages, system, **kwargs)
            )
            content = response.get('content', '')
            
            # Yield the content in chunks (simulate streaming)
            # In a real streaming implementation, you'd yield as data arrives
            if content:
                # Split into chunks for streaming effect
                chunk_size = 50
                for i in range(0, len(content), chunk_size):
                    # Yield with a small async delay to make it properly async
                    await asyncio.sleep(0)
                    # Create LlmStreamChunk object with content
                    yield LlmStreamChunk(
                        content=content[i:i + chunk_size],
                        tool_calls=None,
                        finish_reason=None,
                        metadata={}
                    )
            
            # Yield final chunk with finish_reason
            yield LlmStreamChunk(
                content=None,
                tool_calls=None,
                finish_reason='stop',
                metadata={}
            )
        except Exception as e:
            _logger.error(f'LLM streaming error: {str(e)}')
            raise
    
    def validate_tools(self, tools: List[Any]) -> bool:
        """
        Validate that tools are compatible with this LLM service
        
        Args:
            tools: List of tools to validate
            
        Returns:
            True if tools are valid, False otherwise
        """
        # For llama.cpp, we accept all tools
        # In a more sophisticated implementation, you might check tool schemas
        return True

