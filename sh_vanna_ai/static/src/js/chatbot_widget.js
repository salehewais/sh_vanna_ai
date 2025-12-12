/** @odoo-module **/

import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

export class VannaChatbotWidget extends Component {
    static template = "vanna_ai.ChatbotWidget";

    setup() {
        this.rpc = rpc;
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            isOpen: false,
            isMinimized: false,
            messages: [],
            inputText: "",
            isLoading: false,
            currentContext: null,
        });

        this.chatContainer = useRef("chatContainer");
        this.messageInput = useRef("messageInput");

        onMounted(() => {
            this.updateContext();
        });
    }

    toggleChat() {
        this.state.isOpen = !this.state.isOpen;
        if (this.state.isOpen) {
            this.state.isMinimized = false;
            this.updateContext();
            setTimeout(() => {
                if (this.messageInput.el) {
                    this.messageInput.el.focus();
                }
            }, 100);
        }
    }

    minimizeChat() {
        this.state.isMinimized = !this.state.isMinimized;
    }

    closeChat() {
        this.state.isOpen = false;
    }

    async updateContext() {
        try {
            // Get current action/view context
            const currentAction = this.action.currentController;

            if (currentAction && currentAction.action) {
                const action = currentAction.action;

                this.state.currentContext = {
                    model_name: action.res_model,
                    view_type: action.view_mode,
                    action_name: action.name,
                };

                // If in form view, get current record ID
                if (currentAction.props && currentAction.props.resId) {
                    this.state.currentContext.record_id = currentAction.props.resId;
                }

                // Get field names for the model
                if (action.res_model) {
                    const modelInfo = await this.orm.call(
                        'vanna.chatbot',
                        'get_model_info',
                        [action.res_model]
                    );

                    if (modelInfo && modelInfo.fields) {
                        this.state.currentContext.field_names = modelInfo.fields.map(f => f.name);
                        this.state.currentContext.model_display_name = modelInfo.name;
                    }
                }
            }
        } catch (error) {
            console.error("Error updating context:", error);
        }
    }

    async sendMessage() {
        const text = this.state.inputText.trim();
        if (!text || this.state.isLoading) return;

        // Add user message
        this.addMessage("user", text);
        this.state.inputText = "";
        this.state.isLoading = true;

        try {
            // Update context before sending
            await this.updateContext();

            // Call backend to process query
            const response = await this.orm.call(
                'vanna.chatbot',
                'process_query',
                [text],
                {
                    context: this.state.currentContext
                }
            );

            if (response.error) {
                this.addMessage("error", response.message || "An error occurred");
            } else {
                // Add AI response
                this.addMessage("assistant", response.response);

                // If SQL was generated, show it
                if (response.sql) {
                    this.addMessage("sql", response.sql);
                }

                // If results are available, format them
                if (response.results && response.results.rows) {
                    const resultsText = this.formatResults(response.results);
                    this.addMessage("results", resultsText);
                }
            }
        } catch (error) {
            console.error("Error sending message:", error);
            this.addMessage("error", "Failed to communicate with AI assistant: " + error.message);
        } finally {
            this.state.isLoading = false;
            this.scrollToBottom();
        }
    }

    addMessage(type, content) {
        this.state.messages.push({
            type,
            content,
            timestamp: new Date().toLocaleTimeString(),
        });
        setTimeout(() => this.scrollToBottom(), 100);
    }

    formatResults(results) {
        if (!results || !results.rows || results.rows.length === 0) {
            return "No results found.";
        }

        let text = `Found ${results.count} result(s):\n\n`;

        const displayRows = results.rows.slice(0, 10);

        for (const row of displayRows) {
            results.columns.forEach((col, idx) => {
                text += `${col}: ${row[idx]}\n`;
            });
            text += "\n";
        }

        if (results.count > 10) {
            text += `... and ${results.count - 10} more results`;
        }

        return text;
    }

    scrollToBottom() {
        if (this.chatContainer.el) {
            this.chatContainer.el.scrollTop = this.chatContainer.el.scrollHeight;
        }
    }

    onKeyPress(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.sendMessage();
        }
    }

    clearChat() {
        this.state.messages = [];
        this.addMessage("system", "Chat cleared. How can I help you?");
    }

    getContextSummary() {
        if (!this.state.currentContext) {
            return "No context available";
        }

        const ctx = this.state.currentContext;
        let summary = "";

        if (ctx.model_display_name) {
            summary += `Model: ${ctx.model_display_name}`;
        } else if (ctx.model_name) {
            summary += `Model: ${ctx.model_name}`;
        }

        if (ctx.record_id) {
            summary += ` | Record ID: ${ctx.record_id}`;
        }

        return summary || "General context";
    }
}

// Register the widget as a systray item
export const systrayItem = {
    Component: VannaChatbotWidget,
};

registry.category("systray").add("vanna_chatbot", systrayItem, { sequence: 100 });