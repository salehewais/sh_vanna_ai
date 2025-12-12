import logging
import asyncio
from odoo import models, api
from odoo.exceptions import UserError
from .vanna_llm_service import LocalLlamaCppLlmService
from .vanna_sql_tool import OdooSqlTool
from .vanna_user_resolver import OdooUserResolver
from .vanna_agent_memory import NoOpAgentMemory
from vanna import Agent
from vanna.core.registry import ToolRegistry
from vanna.core.user import RequestContext

_logger = logging.getLogger(__name__)


class VannaChatbot(models.Model):
    _name = 'vanna.chatbot'
    _description = 'Vanna AI Chatbot Service'

    def _get_agent(self, config):
        """
        Get or create Vanna 2.0 Agent instance
        
        Args:
            config: Vanna config record
            
        Returns:
            Agent instance
        """
        # Create LLM service
        llm_url = f"http://localhost:{config.llm_port}/completion"
        llm_service = LocalLlamaCppLlmService(
            llm_url=llm_url,
            temperature=0.1,
            max_tokens=500
        )

        # Create SQL tool with Odoo environment
        # Store env reference in the tool
        sql_tool = OdooSqlTool(env=self.env)

        # Create tool registry and register tool
        # ToolRegistry uses register_local_tool(tool, access_groups) method
        tool_registry = ToolRegistry()
        # Register tool with no access restrictions (empty list means accessible to all)
        tool_registry.register_local_tool(sql_tool, access_groups=[])

        # Create user resolver and agent memory
        user_resolver = OdooUserResolver(env=self.env)
        agent_memory = NoOpAgentMemory()

        # Create agent with all required parameters
        agent = Agent(
            llm_service=llm_service,
            tool_registry=tool_registry,
            user_resolver=user_resolver,
            agent_memory=agent_memory
        )

        return agent

    def _build_system_prompt(self, context):
        """
        Build system prompt with Odoo context and schema information
        
        Args:
            context: Dict with model_name, record_id, field_names
            
        Returns:
            System prompt string
        """
        prompt_parts = [
            "You are a helpful AI assistant for Odoo, an ERP system.",
            "You can answer questions about the database and execute SQL queries.",
            "When users ask about data, use the run_sql tool to query the database.",
            "Only SELECT queries are allowed for safety.",
            ""
        ]

        # Add schema information
        schema_info = self.env['ir.config_parameter'].sudo().get_param('vanna.schema_info')
        if schema_info:
            import json
            try:
                schema = json.loads(schema_info)
                prompt_parts.append("Available database tables:")
                for table_info in schema[:10]:  # Limit to first 10 tables
                    prompt_parts.append(f"- {table_info['table']} ({table_info['name']})")
                prompt_parts.append("")
            except:
                pass

        # Add current context
        if context:
            if context.get('model_name'):
                model = self.env['ir.model'].search([
                    ('model', '=', context['model_name'])
                ], limit=1)

                if model:
                    table_name = model.model.replace('.', '_')
                    prompt_parts.append(f"Current context: Table '{table_name}' ({model.name})")

                    if context.get('field_names'):
                        fields = self.env['ir.model.fields'].search([
                            ('model_id', '=', model.id),
                            ('name', 'in', context['field_names'])
                        ], limit=10)

                        if fields:
                            prompt_parts.append("Relevant fields:")
                            for field in fields:
                                prompt_parts.append(f"  - {field.name} ({field.ttype}): {field.field_description}")

                    if context.get('record_id'):
                        prompt_parts.append(f"Current record ID: {context['record_id']}")

                    prompt_parts.append("")

        return "\n".join(prompt_parts)

    @api.model
    def process_query(self, question, context=None):
        """
        Process a user query with context awareness using Vanna 2.0 Agent

        Args:
            question: User's question
            context: Dict with model_name, record_id, field_names

        Returns:
            Dict with response and any SQL results
        """
        try:
            config = self.env['vanna.config'].search([], limit=1)
            if not config or config.llm_status != 'running':
                return {
                    'error': True,
                    'message': 'LLM server is not running. Please configure and start it first.'
                }

            # Get agent
            agent = self._get_agent(config)
            
            # Create request context (empty, since we use Odoo env directly in resolver)
            request_context = RequestContext(
                cookies={},
                headers={},
                remote_addr=None,
                query_params={},
                metadata={'odoo_env': self.env}  # Pass env in metadata for resolver
            )
            
            # Process query using agent
            # Note: Vanna 2.0 Agent.send_message is async, so we need to handle it
            try:
                # Try to get existing event loop
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                # Run the agent send_message
                # send_message returns an async generator, so we need to collect all components
                if loop.is_running():
                    # If loop is already running, we need to use a different approach
                    # For Odoo, we'll use run_until_complete in a new thread
                    import concurrent.futures
                    async def collect_response():
                        components = []
                        async for component in agent.send_message(request_context, question):
                            components.append(component)
                        return components
                    
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            collect_response()
                        )
                        components = future.result(timeout=60)
                else:
                    async def collect_response():
                        components = []
                        async for component in agent.send_message(request_context, question):
                            components.append(component)
                        return components
                    
                    components = loop.run_until_complete(collect_response())
                
                _logger.info(f'Received {len(components)} components from agent')
                
                # Process components into response
                response = self._process_agent_components(components)
                _logger.info(f'Processed response: {response}')
                result = response
                
            except Exception as async_error:
                _logger.error(f'Async execution error: {str(async_error)}', exc_info=True)
                result = {
                    'error': True,
                    'message': f'Error processing query: {str(async_error)}'
                }
            
            return result

        except Exception as e:
            _logger.error(f'Chatbot error: {str(e)}', exc_info=True)
            return {
                'error': True,
                'message': f'Error processing query: {str(e)}'
            }
    
    def _process_agent_components(self, components):
        """
        Process UI components from Agent.send_message into response format
        
        Args:
            components: List of UI components from agent
            
        Returns:
            Dict with response, sql, and results
        """
        result = {
            'response': '',
            'sql': None,
            'results': None,
            'error': False
        }
        
        if not components:
            result['response'] = 'No response generated.'
            return result
        
        # Process components
        for component in components:
            try:
                # Check component type and extract relevant information
                component_type = type(component).__name__
                _logger.debug(f'Processing component type: {component_type}, component: {component}')
                
                # UiComponent has rich_component and simple_component
                # Extract the actual component data
                actual_component = None
                if hasattr(component, 'rich_component'):
                    actual_component = component.rich_component
                elif hasattr(component, 'simple_component') and component.simple_component:
                    actual_component = component.simple_component
                else:
                    actual_component = component
                
                # Try to get component as dict first (Pydantic models can be converted)
                if hasattr(actual_component, 'model_dump'):
                    component_dict = actual_component.model_dump()
                elif hasattr(actual_component, 'dict'):
                    component_dict = actual_component.dict()
                elif hasattr(component, 'model_dump'):
                    component_dict = component.model_dump()
                elif hasattr(component, 'dict'):
                    component_dict = component.dict()
                else:
                    component_dict = {}
                
                _logger.debug(f'Component dict: {component_dict}')
                
                # Check for text content in simple_component or rich_component
                if hasattr(actual_component, 'text'):
                    text = actual_component.text
                    if text:
                        result['response'] += str(text) + '\n'
                elif 'text' in component_dict:
                    result['response'] += str(component_dict['text']) + '\n'
                elif hasattr(actual_component, 'content'):
                    content = actual_component.content
                    if content:
                        result['response'] += str(content) + '\n'
                elif 'content' in component_dict:
                    result['response'] += str(component_dict['content']) + '\n'
                
                # Check for SQL
                if hasattr(actual_component, 'sql'):
                    result['sql'] = actual_component.sql
                elif 'sql' in component_dict:
                    result['sql'] = component_dict['sql']
                
                # Check for table/data
                if hasattr(actual_component, 'data') or hasattr(actual_component, 'rows'):
                    data = getattr(actual_component, 'data', getattr(actual_component, 'rows', []))
                    columns = getattr(actual_component, 'columns', [])
                    if data:
                        result['results'] = {
                            'columns': columns if columns else [],
                            'rows': data if isinstance(data, list) else [data],
                            'count': len(data) if isinstance(data, list) else 1
                        }
                elif 'data' in component_dict:
                    result['results'] = {
                        'columns': component_dict.get('columns', []),
                        'rows': component_dict.get('data', []),
                        'count': len(component_dict.get('data', []))
                    }
                
                # Fallback: try to convert component to string
                if not result['response'] and not result['sql'] and not result['results']:
                    component_str = str(actual_component)
                    if component_str and component_str not in ['None', '']:
                        result['response'] += component_str + '\n'
                        
            except Exception as e:
                _logger.warning(f'Error processing component {component}: {str(e)}', exc_info=True)
                # Try to add as string as fallback
                try:
                    result['response'] += str(component) + '\n'
                except:
                    pass
        
        # Clean up response
        result['response'] = result['response'].strip()
        
        # If no response at all, add a default message
        if not result['response'] and not result['sql'] and not result['results']:
            result['response'] = 'I received your message but could not generate a response.'
        
        return result

    @api.model
    def get_model_info(self, model_name):
        """Get information about an Odoo model"""
        try:
            model = self.env['ir.model'].search([
                ('model', '=', model_name)
            ], limit=1)

            if not model:
                return {'error': f'Model {model_name} not found'}

            fields = self.env['ir.model.fields'].search([
                ('model_id', '=', model.id)
            ])

            field_info = [{
                'name': f.name,
                'description': f.field_description,
                'type': f.ttype,
                'required': f.required,
            } for f in fields]

            return {
                'name': model.name,
                'model': model.model,
                'info': model.info,
                'fields': field_info
            }

        except Exception as e:
            return {'error': str(e)}
