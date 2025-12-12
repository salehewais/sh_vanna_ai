import os
import subprocess
import logging
import threading
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json

_logger = logging.getLogger(__name__)


class VannaConfig(models.Model):
    _name = 'vanna.config'
    _description = 'Vanna AI Configuration'
    _rec_name = 'llm_backend'

    llm_backend = fields.Selection([
        ('qwen2b', 'Qwen-2B-Small'),
        ('tinyllama', 'TinyLlama'),
        ('custom', 'Custom llama.cpp Model'),
    ], string='LLM Backend', required=True, default='qwen2b')

    custom_model_url = fields.Char('Custom Model URL',
                                   help='URL to download custom GGUF model')

    llm_status = fields.Selection([
        ('not_installed', 'Not Installed'),
        ('downloading', 'Downloading'),
        ('installing', 'Installing'),
        ('running', 'Running'),
        ('stopped', 'Stopped'),
        ('error', 'Error'),
    ], string='LLM Status', default='not_installed', readonly=True)

    llm_port = fields.Char('LLM Server Port', default='8080')
    vanna_trained = fields.Boolean('Vanna Trained', default=False)
    server_path = fields.Char('Server Path', readonly=True)
    model_path = fields.Char('Model Path', readonly=True)
    error_message = fields.Text('Error Message', readonly=True)

    def _get_base_path(self):
        """Get base path for storing models and server"""
        base = os.path.join(os.path.expanduser('~'), '.odoo_vanna')
        os.makedirs(base, exist_ok=True)
        return base

    def _get_model_info(self):
        """Get download URL and filename for selected model"""
        models = {
            'qwen2b': {
                'url': 'https://huggingface.co/Qwen/Qwen2-0.5B-Instruct-GGUF/resolve/main/qwen2-0_5b-instruct-q4_0.gguf',
                'filename': 'qwen2-0.5b-instruct-q4_0.gguf',
            },
            'tinyllama': {
                'url': 'https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf',
                'filename': 'tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf',
            },
        }

        if self.llm_backend == 'custom' and self.custom_model_url:
            return {
                'url': self.custom_model_url,
                'filename': os.path.basename(self.custom_model_url),
            }

        return models.get(self.llm_backend)

    def action_download_and_setup(self):
        """Download llama.cpp and model, then start server"""
        self.ensure_one()

        try:
            self.llm_status = 'downloading'
            base_path = self._get_base_path()

            # Download and setup llama.cpp
            server_path = self._setup_llamacpp(base_path)
            self.server_path = server_path

            # Download model
            model_info = self._get_model_info()
            if not model_info:
                raise UserError(_('Invalid model configuration'))

            model_path = self._download_model(base_path, model_info)
            self.model_path = model_path

            # Start server
            self.llm_status = 'installing'
            self._start_llm_server()

            # Train Vanna
            self._train_vanna()

            self.llm_status = 'running'
            self.error_message = False

            self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification', {
                'type': 'success',
                'message': _('LLM server started successfully'),
            })

            return True

        except Exception as e:
            _logger.error(f'Error setting up LLM: {str(e)}')
            self.llm_status = 'error'
            self.error_message = str(e)
            raise UserError(_(f'Setup failed: {str(e)}'))

    def _setup_llamacpp(self, base_path):
        """Download and compile llama.cpp"""
        llamacpp_path = os.path.join(base_path, 'llama.cpp')
        
        # Possible server binary paths (depending on build method)
        # Note: cmake builds create llama-server in build/bin/
        server_paths = [
            os.path.join(llamacpp_path, 'build', 'bin', 'llama-server'),  # cmake build path (correct)
            os.path.join(llamacpp_path, 'build', 'bin', 'server'),  # alternative name
            os.path.join(llamacpp_path, 'build', 'server'),  # alternative cmake path
            os.path.join(llamacpp_path, 'server'),  # make build path
        ]
        
        # Check if server already exists
        for server_path in server_paths:
            if os.path.exists(server_path):
                _logger.info(f'llama.cpp server already built at {server_path}')
                return server_path

        # Check if directory exists (from previous clone)
        if os.path.exists(llamacpp_path):
            # Check if it's a git repository
            if os.path.exists(os.path.join(llamacpp_path, '.git')):
                _logger.info('llama.cpp directory exists, skipping clone. Updating repository...')
                # Try to update the repository
                try:
                    subprocess.run(['git', 'pull'], cwd=llamacpp_path, check=True, 
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                except subprocess.CalledProcessError:
                    _logger.warning('Could not update repository, continuing with existing code')
            else:
                # Directory exists but is not a git repo, remove it
                _logger.warning(f'Directory {llamacpp_path} exists but is not a git repository. Removing it...')
                import shutil
                shutil.rmtree(llamacpp_path)
                _logger.info('Cloning llama.cpp repository...')
                subprocess.run([
                    'git', 'clone',
                    'https://github.com/ggerganov/llama.cpp.git',
                    llamacpp_path
                ], check=True)
        else:
            _logger.info('Cloning llama.cpp repository...')
            # Clone repo
            subprocess.run([
                'git', 'clone',
                'https://github.com/ggerganov/llama.cpp.git',
                llamacpp_path
            ], check=True)

        # Build
        _logger.info('Building llama.cpp...')
        subprocess.run(['cmake', '-B', 'build'], cwd=llamacpp_path, check=True)
        subprocess.run(['cmake', '--build', 'build', '--config', 'Release'], cwd=llamacpp_path, check=True)

        # Check for server binary in possible locations
        for server_path in server_paths:
            if os.path.exists(server_path):
                _logger.info(f'Server binary found at {server_path}')
                return server_path

        raise Exception('Server binary not found after build. Checked paths: ' + ', '.join(server_paths))

    def _download_model(self, base_path, model_info):
        """Download model file"""
        models_path = os.path.join(base_path, 'models')
        os.makedirs(models_path, exist_ok=True)

        model_file = os.path.join(models_path, model_info['filename'])

        if os.path.exists(model_file):
            _logger.info(f'Model already exists: {model_file}')
            return model_file

        _logger.info(f'Downloading model from {model_info["url"]}...')

        response = requests.get(model_info['url'], stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0

        with open(model_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        if downloaded % (10 * 1024 * 1024) == 0:  # Log every 10MB
                            _logger.info(f'Download progress: {progress:.1f}%')

        _logger.info(f'Model downloaded: {model_file}')
        return model_file

    def _start_llm_server(self):
        """Start llama.cpp server in background"""

        def run_server():
            try:
                cmd = [
                    self.server_path,
                    '-m', self.model_path,
                    '--port', str(self.llm_port),
                    '-c', '2048',
                    '--threads', '4',
                ]

                _logger.info(f'Starting LLM server: {" ".join(cmd)}')

                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

                # Store process info
                self.env['ir.config_parameter'].sudo().set_param(
                    'vanna.llm_pid', str(process.pid)
                )

                # Monitor output
                for line in process.stdout:
                    if 'HTTP server listening' in line:
                        _logger.info('LLM server ready')
                        break

            except Exception as e:
                _logger.error(f'Server error: {str(e)}')
                self.llm_status = 'error'
                self.error_message = str(e)

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()

        # Wait for server to be ready
        import time
        for _ in range(30):
            try:
                response = requests.get(f'http://localhost:{self.llm_port}/health', timeout=1)
                if response.status_code == 200:
                    _logger.info('LLM server is healthy')
                    return
            except:
                pass
            time.sleep(1)

        _logger.warning('Could not confirm server health, but continuing...')

    def _train_vanna(self):
        """Initialize and prepare Vanna 2.0 with database schema information"""
        try:
            _logger.info('Preparing Vanna 2.0 schema information...')

            # In Vanna 2.0, we store schema information for context
            # This will be used by the agent to understand the database structure
            schema_info = []

            # Get all models
            models = self.env['ir.model'].search([])
            for model in models[:50]:  # Limit to avoid timeout
                ddl = f"-- Table: {model.model.replace('.', '_')} ({model.name})\n"
                fields = self.env['ir.model.fields'].search([('model_id', '=', model.id)])
                for field in fields:
                    ddl += f"-- Field: {field.name} ({field.field_description}), Type: {field.ttype}\n"

                schema_info.append({
                    'table': model.model.replace('.', '_'),
                    'name': model.name,
                    'ddl': ddl
                })

            # Store schema information as JSON
            import json
            schema_json = json.dumps(schema_info)
            self.env['ir.config_parameter'].sudo().set_param(
                'vanna.schema_info', schema_json
            )

            # Mark as trained
            self.env['ir.config_parameter'].sudo().set_param(
                'vanna.trained', 'true'
            )
            self.vanna_trained = True

            _logger.info(f'Vanna schema information prepared for {len(schema_info)} models')

        except Exception as e:
            _logger.error(f'Vanna schema preparation error: {str(e)}')
            raise

    def action_stop_server(self):
        """Stop the LLM server"""
        self.ensure_one()

        try:
            pid = self.env['ir.config_parameter'].sudo().get_param('vanna.llm_pid')
            if pid:
                import signal
                os.kill(int(pid), signal.SIGTERM)
                self.llm_status = 'stopped'

            self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification', {
                'type': 'info',
                'message': _('LLM server stopped'),
            })

            return True
        except Exception as e:
            raise UserError(_(f'Failed to stop server: {str(e)}'))

    def action_test_connection(self):
        """Test connection to LLM server"""
        self.ensure_one()

        try:
            response = requests.post(
                f'http://localhost:{self.llm_port}/completion',
                json={'prompt': 'Hello', 'max_tokens': 10},
                timeout=5
            )
            response.raise_for_status()

            self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification', {
                'type': 'success',
                'message': _('LLM server is responding'),
            })

            return True
        except Exception as e:
            raise UserError(_(f'Connection failed: {str(e)}'))
