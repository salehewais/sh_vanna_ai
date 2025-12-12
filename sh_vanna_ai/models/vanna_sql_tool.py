"""
Custom SQL Tool for Vanna 2.0 that integrates with Odoo database
"""
import logging
from typing import Type, Optional
from pydantic import BaseModel, Field
from vanna.core.tool import Tool, ToolContext, ToolResult
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class RunSqlArgs(BaseModel):
    """Arguments for running SQL queries"""
    sql: str = Field(description="The SQL SELECT query to execute")
    limit: Optional[int] = Field(default=100, description="Maximum number of rows to return")


class OdooSqlTool(Tool[RunSqlArgs]):
    """SQL Tool that executes queries on Odoo database with safety checks"""
    
    def __init__(self, env=None):
        """
        Initialize the SQL tool
        
        Args:
            env: Odoo environment (will be set via context)
        """
        self.env = env
    
    @property
    def name(self) -> str:
        return "run_sql"
    
    @property
    def description(self) -> str:
        return "Execute a SQL SELECT query on the Odoo database. Only SELECT queries are allowed."
    
    @property
    def access_groups(self) -> list[str]:
        # Allow all authenticated users by default
        # Can be customized based on Odoo groups
        return []
    
    def get_args_schema(self) -> Type[RunSqlArgs]:
        return RunSqlArgs
    
    async def execute(self, context: ToolContext, args: RunSqlArgs) -> ToolResult:
        """
        Execute SQL query with safety checks
        
        Args:
            context: Tool context (contains user info)
            args: SQL query arguments
            
        Returns:
            ToolResult with query results
        """
        try:
            # Get Odoo environment - prefer stored one, fallback to context
            env = self.env
            if not env and hasattr(context, 'env'):
                env = context.env
            
            if not env:
                return ToolResult(
                    success=False,
                    result_for_llm="Odoo environment not available"
                )
            
            sql = args.sql.strip()
            
            # Safety validation
            validation_result = self._validate_sql(sql)
            if not validation_result['valid']:
                return ToolResult(
                    success=False,
                    result_for_llm=validation_result['error']
                )
            
            # Add LIMIT if not present
            sql_upper = sql.upper()
            if 'LIMIT' not in sql_upper:
                sql = f"{sql} LIMIT {args.limit}"
            
            # Execute query
            env.cr.execute(sql)
            
            # Fetch results
            columns = [desc[0] for desc in env.cr.description] if env.cr.description else []
            rows = env.cr.fetchall()
            
            # Format results
            result_data = {
                'columns': columns,
                'rows': rows,
                'count': len(rows)
            }
            
            # Format for LLM
            result_text = self._format_results_for_llm(result_data)
            
            return ToolResult(
                success=True,
                result_for_llm=result_text,
                data=result_data
            )
            
        except Exception as e:
            _logger.error(f'SQL execution error: {str(e)}')
            return ToolResult(
                success=False,
                result_for_llm=f"Error executing SQL: {str(e)}"
            )
    
    def _validate_sql(self, sql: str) -> dict:
        """
        Validate SQL query for safety
        
        Args:
            sql: SQL query string
            
        Returns:
            Dict with 'valid' boolean and optional 'error' message
        """
        sql_upper = sql.upper().strip()
        
        # Check for dangerous keywords
        dangerous_keywords = [
            'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE',
            'ALTER', 'TRUNCATE', 'GRANT', 'REVOKE', 'EXEC',
            'EXECUTE', 'CALL', 'MERGE', 'COPY'
        ]
        
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                return {
                    'valid': False,
                    'error': f'SQL contains forbidden keyword: {keyword}. Only SELECT queries are allowed.'
                }
        
        # Must start with SELECT
        if not sql_upper.startswith('SELECT'):
            return {
                'valid': False,
                'error': 'Only SELECT queries are allowed. Query must start with SELECT.'
            }
        
        return {'valid': True}
    
    def _format_results_for_llm(self, results: dict) -> str:
        """
        Format query results for LLM consumption
        
        Args:
            results: Dict with 'columns', 'rows', and 'count'
            
        Returns:
            Formatted string
        """
        if not results.get('rows'):
            return "No results found."
        
        columns = results['columns']
        rows = results['rows']
        count = results['count']
        
        # Format as a simple table representation
        lines = [f"Found {count} result(s):"]
        lines.append("")
        
        # Show column headers
        if columns:
            lines.append(" | ".join(columns))
            lines.append("-" * (len(" | ".join(columns))))
        
        # Show rows (limit to 10 for LLM)
        display_rows = rows[:10]
        for row in display_rows:
            row_str = " | ".join(str(val) if val is not None else "NULL" for val in row)
            lines.append(row_str)
        
        if count > 10:
            lines.append(f"... and {count - 10} more results")
        
        return "\n".join(lines)

