from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class ChatAnalysisReport(models.Model):
    _name = 'chat.analysis.report'
    _description = 'Chat Analysis Report'
    _rec_name = 'display_name'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    chat_id = fields.Many2one('chat.analysis.chat', string='Chat', required=True, tracking=True)
    user_id = fields.Many2one('chat.analysis.user', string='User', tracking=True)
    analysis_type = fields.Selection([
        ('review', 'Review'),
        ('compliance', 'Compliance Check')
    ], string='Analysis Type', required=True, tracking=True)

    target_datetime = fields.Datetime(string='Target Date/Time', required=True, tracking=True)
    lookback_minutes = fields.Integer(string='Lookback Minutes', default=60)
    lookforward_minutes = fields.Integer(string='Lookforward Minutes', default=60)

    instruction = fields.Text(string='Instruction', help='Instruction for compliance check')

    # Результаты review
    summary = fields.Text(string='Summary')
    sentiment = fields.Selection([
        ('positive', 'Positive'),
        ('neutral', 'Neutral'),
        ('negative', 'Negative')
    ], string='Sentiment')
    key_points = fields.Text(string='Key Points')
    participant_count = fields.Integer(string='Participants')
    message_count = fields.Integer(string='Messages in Window')
    message_count_before = fields.Integer(string='Messages Before Target')
    message_count_after = fields.Integer(string='Messages After Target')

    # Результаты compliance
    compliant = fields.Boolean(string='Compliant', tracking=True)
    confidence = fields.Float(string='Confidence', digits=(3, 2))
    explanation = fields.Text(string='Explanation')
    violations = fields.Text(string='Violations')
    suggestions = fields.Text(string='Suggestions')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('error', 'Error')
    ], string='Status', default='draft', tracking=True)

    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)

    @api.depends('create_date', 'chat_id', 'analysis_type')
    def _compute_display_name(self):
        for report in self:
            report.display_name = f"{report.chat_id.title} - {report.analysis_type} - {report.create_date}"

    def action_process_review(self):
        """Обработка ревью чата"""
        self.ensure_one()
        self.state = 'processing'

        try:
            api_url = self._get_api_url()

            data = {
                'chat_id': self.chat_id.external_id,
                'target_datetime': self.target_datetime.isoformat(),
                'lookback_minutes': self.lookback_minutes,
                'lookforward_minutes': self.lookforward_minutes
            }

            response = requests.post(
                f"{api_url}/analysis/review",
                json=data,
                headers=self._get_headers(),
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                self.summary = result.get('summary')
                self.sentiment = result.get('sentiment')
                self.key_points = '\n'.join(result.get('key_points', []))
                self.participant_count = result.get('participant_count')
                self.message_count = result.get('message_count')
                self.message_count_before = result.get('message_count_before')
                self.message_count_after = result.get('message_count_after')
                self.state = 'completed'

                self.message_post(
                    body=f"Review completed for {self.chat_id.title}",
                    subject="Review Completed"
                )
            else:
                raise UserError(f"API Error: {response.text}")

        except Exception as e:
            self.state = 'error'
            self.summary = f"Error: {str(e)}"
            _logger.error(f"Review processing failed: {e}")
            raise UserError(f"Review failed: {str(e)}")

    def action_process_compliance(self):
        """Обработка проверки соответствия"""
        self.ensure_one()
        if not self.instruction:
            raise UserError("Instruction is required for compliance check")

        self.state = 'processing'

        try:
            api_url = self._get_api_url()

            data = {
                'chat_id': self.chat_id.external_id,
                'target_datetime': self.target_datetime.isoformat(),
                'description': self.instruction,
                'lookback_minutes': self.lookback_minutes,
                'lookforward_minutes': self.lookforward_minutes
            }

            response = requests.post(
                f"{api_url}/analysis/compliance",
                json=data,
                headers=self._get_headers(),
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                self.compliant = result.get('compliant')
                self.confidence = result.get('confidence')
                self.explanation = result.get('explanation')
                self.violations = '\n'.join(result.get('violations', []))
                self.suggestions = '\n'.join(result.get('suggestions', []))
                self.state = 'completed'

                if not self.compliant and self.confidence < 0.5:
                    self._create_ticket_from_violations()

                self.message_post(
                    body=f"Compliance check completed: {'Compliant' if self.compliant else 'Non-compliant'}",
                    subject="Compliance Check Completed"
                )
            else:
                raise UserError(f"API Error: {response.text}")

        except Exception as e:
            self.state = 'error'
            self.explanation = f"Error: {str(e)}"
            _logger.error(f"Compliance check failed: {e}")
            raise UserError(f"Compliance check failed: {str(e)}")

    def _create_ticket_from_violations(self):
        """Создаёт задачу на основе нарушений"""
        try:
            ticket = self.env['chat.analysis.ticket'].create({
                'name': f"Violation in {self.chat_id.title}",
                'report_id': self.id,
                'chat_id': self.chat_id.id,
                'description': self.explanation,
                'violations': self.violations,
                'priority': 'high' if self.confidence < 0.3 else 'normal',
            })

            self.message_post(
                body=f"Ticket created: <a href=# data-oe-model=chat.analysis.ticket data-oe-id={ticket.id}>{ticket.name}</a>",
                subject="Ticket Created"
            )
            return ticket
        except Exception as e:
            _logger.error(f"Failed to create ticket: {e}")
            return None

    def _get_api_url(self):
        """Получает URL API из настроек"""
        config = self.env['ir.config_parameter'].sudo()
        base_url = config.get_param('chat_analysis.api_url', 'http://chat_api:8000')
        return base_url.rstrip('/') + '/api/v1'

    def _get_headers(self):
        """Получает заголовки для API запроса"""
        config = self.env['ir.config_parameter'].sudo()
        api_key = config.get_param('chat_analysis.api_key', '')
        return {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

    def action_view_chart(self):
        """Открывает аналитику для текущего отчёта"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Analytics',
            'res_model': 'chat.analysis.report',
            'view_mode': 'graph,pivot',
            'res_id': self.id,
            'target': 'current',
            'context': {
                'search_default_group_by_type': 1,
            },
        }

    def action_retry_failed(self):
        """Повторить失败的 отчёт"""
        self.ensure_one()

        if self.analysis_type == 'review':
            return self.action_process_review()
        else:
            return self.action_process_compliance()

    def action_export_report(self):
        """Экспорт отчёта в HTML"""
        self.ensure_one()

        if self.analysis_type == 'review':
            content = f"""
            <html>
            <head><meta charset="utf-8"><title>Review Report</title></head>
            <body>
                <h1>Review Report for {self.chat_id.title}</h1>
                <p><strong>Date:</strong> {self.create_date}</p>
                <p><strong>Target Time:</strong> {self.target_datetime}</p>
                <h2>Summary</h2>
                <p>{self.summary or 'No summary'}</p>
                <h2>Sentiment</h2>
                <p>{self.sentiment or 'Unknown'}</p>
                <h2>Key Points</h2>
                <p>{self.key_points or 'No key points'}</p>
                <h2>Statistics</h2>
                <ul>
                    <li>Participants: {self.participant_count}</li>
                    <li>Messages in window: {self.message_count}</li>
                    <li>Messages before: {self.message_count_before}</li>
                    <li>Messages after: {self.message_count_after}</li>
                </ul>
            </body>
            </html>
            """
        else:
            content = f"""
            <html>
            <head><meta charset="utf-8"><title>Compliance Report</title></head>
            <body>
                <h1>Compliance Report for {self.chat_id.title}</h1>
                <p><strong>Date:</strong> {self.create_date}</p>
                <p><strong>Target Time:</strong> {self.target_datetime}</p>
                <h2>Compliance Status</h2>
                <p><strong>Compliant:</strong> {'Yes' if self.compliant else 'No'}</p>
                <p><strong>Confidence:</strong> {(self.confidence or 0) * 100:.1f}%</p>
                <h2>Explanation</h2>
                <p>{self.explanation or 'No explanation'}</p>
                <h2>Violations</h2>
                <p>{self.violations or 'No violations'}</p>
                <h2>Suggestions</h2>
                <p>{self.suggestions or 'No suggestions'}</p>
            </body>
            </html>
            """

        attachment = self.env['ir.attachment'].create({
            'name': f'report_{self.id}.html',
            'datas': content.encode('utf-8'),
            'res_model': 'chat.analysis.report',
            'res_id': self.id,
            'mimetype': 'text/html',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }


class ChatAnalysisMessage(models.Model):
    _name = 'chat.analysis.message'
    _description = 'Chat Message'
    _order = 'timestamp desc'
    _rec_name = 'display_name'

    external_id = fields.Char(string='External ID', index=True)
    message_id = fields.Char(string='Message ID', required=True)
    chat_id = fields.Many2one('chat.analysis.chat', string='Chat', required=True, ondelete='cascade')
    user_id = fields.Many2one('chat.analysis.user', string='Sender', required=True)
    sender_name = fields.Char(string='Sender Name')
    content = fields.Text(string='Content')
    timestamp = fields.Datetime(string='Timestamp', required=True)
    reply_to_message_id = fields.Char(string='Reply To')

    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)

    @api.depends('sender_name', 'timestamp')
    def _compute_display_name(self):
        for msg in self:
            msg.display_name = f"[{msg.timestamp}] {msg.sender_name}: {msg.content[:50]}..."

    def action_view_in_chat(self):
        """Открыть сообщение в контексте чата"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Chat Messages',
            'res_model': 'chat.analysis.message',
            'view_mode': 'tree,form',
            'domain': [('chat_id', '=', self.chat_id.id)],
            'context': {'default_chat_id': self.chat_id.id},
        }


class ChatAnalysisTicket(models.Model):
    _name = 'chat.analysis.ticket'
    _description = 'Chat Analysis Ticket'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Ticket Name', required=True)
    report_id = fields.Many2one('chat.analysis.report', string='Report')
    chat_id = fields.Many2one('chat.analysis.chat', string='Chat', required=True)
    description = fields.Text(string='Description')
    violations = fields.Text(string='Violations')

    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent')  # Было 'urg*******'
    ], string='Priority', default='normal')

    state = fields.Selection([
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed')
    ], string='Status', default='new', tracking=True)

    assigned_to = fields.Many2one('res.users', string='Assigned To')

    def action_mark_in_progress(self):
        self.state = 'in_progress'

    def action_mark_resolved(self):
        self.state = 'resolved'

    def action_mark_closed(self):
        self.state = 'closed'

    def action_reopen(self):
        """Reopen ticket"""
        self.state = 'in_progress'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Ticket reopened'),
                'type': 'success',
            }
        }

    def _check_api_connection(self):
        """Проверка подключения к API"""
        try:
            api_url = self._get_api_url()
            response = requests.get(
                f"{api_url.replace('/api/v1', '')}/health",
                headers=self._get_headers(),
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
