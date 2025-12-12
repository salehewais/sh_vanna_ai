"""
Simple UserResolver for Odoo integration with Vanna 2.0
"""
from vanna.core.user.resolver import UserResolver
from vanna.core.user import User, RequestContext


class OdooUserResolver(UserResolver):
    """UserResolver that creates User from Odoo environment"""
    
    def __init__(self, env):
        """
        Initialize with Odoo environment
        
        Args:
            env: Odoo environment
        """
        self.env = env
    
    async def resolve_user(self, request_context: RequestContext) -> User:
        """
        Resolve user from Odoo environment
        
        Args:
            request_context: Request context (contains Odoo env in metadata)
            
        Returns:
            User object from Odoo
        """
        # Get Odoo env from metadata or use stored one
        env = request_context.metadata.get('odoo_env', self.env)
        
        # Get current Odoo user
        odoo_user = env.user
        
        return User(
            id=str(odoo_user.id),
            email=odoo_user.email or '',
            group_memberships=[]  # Can be enhanced to get actual Odoo groups
        )

