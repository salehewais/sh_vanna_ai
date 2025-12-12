{
    'name': 'Vanna AI Assistant',
    'version': '18.0.1.0.0',
    'category': 'Tools',
    'summary': 'AI-powered chatbot with Vanna SQL generation and local LLM',
    'description': """
        Integrate Vanna AI with local LLM models for intelligent database queries.
        Features:
        - Local LLM support (Qwen-2B-Small, TinyLlama, llama.cpp models)
        - Automatic model download and setup
        - Vanna SQL generation
        - Floating chatbot widget in all views
        - Context-aware queries based on current Odoo model
    """,
    'author': 'Saleh Hassan',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/vanna_config_views.xml',
        # 'views/templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sh_vanna_ai/static/src/js/chatbot_widget.js',
            'sh_vanna_ai/static/src/xml/chatbot_widget.xml',
            'sh_vanna_ai/static/src/css/chatbot_widget.css',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
