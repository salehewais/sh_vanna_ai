# Vanna AI Assistant for Odoo 18

An intelligent AI-powered chatbot module for Odoo 18 that integrates Vanna SQL generation with local LLM models, providing context-aware assistance across all Odoo views.

## Features

- 🤖 **Local LLM Integration**: Support for Qwen-2B-Small, TinyLlama, and custom llama.cpp models
- 🔍 **Vanna SQL Generation**: Automatically generates and executes SQL queries based on natural language
- 📊 **Context-Aware**: Understands the current Odoo model, fields, and record context
- 💬 **Floating Widget**: Accessible chatbot in all Odoo views (tree, form, kanban, etc.)
- ⚡ **Automatic Setup**: One-click download and configuration of models
- 🔒 **Safe SQL Execution**: Only SELECT queries allowed with automatic safety checks

## Requirements

### System Requirements
- Linux or macOS (Windows with WSL)
- Git
- C++ compiler (gcc/g++ or clang)
- Make
- Python 3.8+
- 4GB+ RAM
- 5GB+ disk space for models

### Python Dependencies
```bash
pip install -r requirements.txt
```

## Installation

### 1. Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y git build-essential cmake
```

**macOS:**
```bash
brew install git cmake
```

### 2. Install Python Requirements
```bash
cd /path/to/odoo/addons/vanna_ai
pip3 install -r requirements.txt
```

### 3. Install the Module in Odoo

1. Copy the `vanna_ai` folder to your Odoo addons directory
2. Restart Odoo server
3. Go to Apps → Update Apps List
4. Search for "Vanna AI Assistant"
5. Click Install

### 4. Configure the Module

1. Go to **Vanna AI → Configuration**
2. Create a new configuration
3. Select your preferred LLM backend:
    - **Qwen-2B-Small**: ~500MB, efficient and fast
    - **TinyLlama**: ~600MB, lightweight
    - **Custom**: Provide URL to any GGUF model from Hugging Face
4. Click **"Download & Start Server"**
5. Wait for status to change to "Running" (may take 5-15 minutes)

## Usage

### Accessing the Chatbot

Once configured, a floating AI button appears in the bottom-right corner of every Odoo screen.

### Example Questions

**General Questions:**
- "What fields are available in this model?"
- "Explain the purpose of this table"
- "What is the current record about?"

**Database Queries:**
- "How many records are in this table?"
- "Show me the top 10 customers by sales"
- "List all active products"
- "What's the total revenue this month?"
- "Count partners by country"

**Context-Aware:**
The chatbot automatically knows:
- Current model/table you're viewing
- Available fields and their types
- Current record ID (in form view)
- Record data

## Module Structure

```
vanna_ai/
├── __init__.py
├── __manifest__.py
├── requirements.txt
├── README.md
├── models/
│   ├── __init__.py
│   ├── vanna_config.py      # Configuration and LLM setup
│   └── vanna_chatbot.py     # Chatbot logic and SQL generation
├── views/
│   ├── vanna_config_views.xml
│   └── templates.xml
├── security/
│   └── ir.model.access.csv
└── static/
    └── src/
        ├── js/
        │   └── chatbot_widget.js    # Frontend widget
        ├── xml/
        │   └── chatbot_widget.xml   # Widget template
        └── css/
            └── chatbot_widget.css   # Styling
```

## Technical Details

### Architecture

1. **LLM Backend**: Uses llama.cpp as local inference server
2. **Vanna Integration**: Custom Vanna class that routes prompts to local LLM
3. **SQL Safety**: Validates and sanitizes all SQL queries
4. **Context Gathering**: Automatically extracts model metadata from Odoo
5. **Frontend Widget**: OWL component that appears in all views

### Configuration Model (`vanna.config`)

Handles:
- Model selection and download
- llama.cpp compilation and setup
- Server process management
- Vanna training with Odoo schema

### Chatbot Model (`vanna.chatbot`)

Handles:
- Query processing
- Context-aware prompt building
- SQL generation via Vanna
- Safe SQL execution
- Result formatting

### Frontend Widget

Built with Odoo OWL framework:
- Systray integration
- Context extraction from current view
- Real-time chat interface
- Message history
- Loading states

## Customization

### Using Custom Models

1. Find a GGUF model on Hugging Face
2. Copy the direct download URL
3. In configuration, select "Custom" backend
4. Paste the model URL
5. Click "Download & Start Server"

### Adjusting Server Settings

Edit `vanna_config.py` in `_start_llm_server()`:

```python
cmd = [
    self.server_path,
    '-m', self.model_path,
    '--port', str(self.llm_port),
    '-c', '2048',           # Context size
    '--threads', '4',       # CPU threads
    '--n-gpu-layers', '0',  # GPU layers (if available)
]
```

### Extending Chatbot Capabilities

Edit `vanna_chatbot.py` to add custom handlers:

```python
def _handle_custom_query(self, question, context):
    # Add your custom logic
    pass
```

## Troubleshooting

### Server Won't Start

- Check system dependencies are installed
- Verify sufficient disk space
- Check error message in configuration form
- Review Odoo logs for detailed errors

### Model Download Fails

- Check internet connection
- Verify URL is correct for custom models
- Try a different model
- Check firewall/proxy settings

### SQL Queries Not Working

- Verify Vanna training completed (check "Vanna Trained" field)
- Test connection using "Test Connection" button
- Check PostgreSQL credentials
- Review chatbot logs for SQL errors

### Widget Not Appearing

- Clear browser cache
- Restart Odoo server
- Check JavaScript console for errors
- Verify assets are loaded

## Performance Tips

1. **Choose Appropriate Model**: Smaller models (Qwen-0.5B, TinyLlama) are faster
2. **Limit Training Data**: Module trains on first 50 models by default
3. **Adjust Context Size**: Reduce `-c` parameter for faster inference
4. **Use GPU**: Add `--n-gpu-layers` if GPU available
5. **Limit Result Sets**: Queries automatically limited to 100 rows

## Security Considerations

- Only SELECT queries allowed
- SQL injection protection via parameterization
- Dangerous keywords blocked (INSERT, UPDATE, DELETE, etc.)
- Results limited to prevent memory issues
- Server runs locally (not exposed to internet)

## Known Limitations

- Training limited to 50 models (configurable)
- Local models are less capable than cloud LLMs
- SQL generation accuracy depends on model quality
- Large result sets may take time to format
- Server restart required after Odoo restart

## Future Enhancements

- [ ] GPU acceleration support
- [ ] Multi-language support
- [ ] Query history and favorites
- [ ] Export results to Excel/CSV
- [ ] Visual query builder
- [ ] Integration with Odoo reports
- [ ] Voice input support
- [ ] Scheduled query execution

## License

LGPL-3

## Support

For issues and questions:
- Check the troubleshooting section
- Review Odoo logs at `/var/log/odoo/`
- Submit issues to your repository

## Credits

- Built on [Vanna AI](https://github.com/vanna-ai/vanna)
- Uses [llama.cpp](https://github.com/ggerganov/llama.cpp)
- Models from Hugging Face community

## Version History

### 1.0.0
- Initial release
- Support for Qwen-2B-Small and TinyLlama
- Context-aware chatbot widget
- Automatic SQL generation
- Safe query execution