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
    user_id = fields.Many2one('res.users', string='Created By', default=lambda self: self.env.user, tracking=True)
    analysis_type = fields.Selection([
        ('review', 'Review'),
        ('compliance', 'Compliance Check')
    ], string='Analysis Type', required=True, tracking=True)

    # Period-based fields
    date_start = fields.Datetime(string='Start Date', required=True, tracking=True)
    date_end = fields.Datetime(string='End Date', required=True, tracking=True)
    instruction = fields.Text(string='Instruction', help='Instruction for compliance check')
    instruction_domain = fields.Char(string='Instruction Domain',
                                     help='Domain/context of the instruction (e.g., customer support, sales, etc.)')

    # Review results
    summary = fields.Text(string='Summary')
    sentiment = fields.Selection([
        ('positive', 'Positive'),
        ('neutral', 'Neutral'),
        ('negative', 'Negative')
    ], string='Sentiment')
    key_points = fields.Text(string='Key Points')
    participant_count = fields.Integer(string='Participants')
    message_count = fields.Integer(string='Messages in Period')
    communication_style = fields.Char(string='Communication Style')
    recommendations = fields.Text(string='Recommendations')

    # Compliance results
    compliant = fields.Boolean(string='Compliant', tracking=True)
    confidence = fields.Float(string='Confidence', digits=(3, 2))
    explanation = fields.Text(string='Explanation')
    violations = fields.Text(string='Violations')
    suggestions = fields.Text(string='Suggestions')
    severe_violations = fields.Integer(string='Severe Violations')
    minor_violations = fields.Integer(string='Minor Violations')

    # Status and tracking
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('error', 'Error')
    ], string='Status', default='draft', tracking=True)

    task_id = fields.Char(string='Task ID', help='Celery task ID for async analysis')
    error_message = fields.Text(string='Error Message')
    analysis_duration = fields.Float(string='Analysis Duration (seconds)')
    analysis_started_at = fields.Datetime(string='Analysis Started At')
    analysis_completed_at = fields.Datetime(string='Analysis Completed At')

    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)

    @api.depends('create_date', 'chat_id', 'analysis_type', 'date_start', 'date_end')
    def _compute_display_name(self):
        type_display = {
            'review': 'Review',
            'compliance': 'Compliance Check'
        }
        for report in self:
            if report.date_start and report.date_end:
                period = f"{report.date_start.strftime('%Y-%m-%d')} - {report.date_end.strftime('%Y-%m-%d')}"
            else:
                period = ""
            type_name = type_display.get(report.analysis_type, report.analysis_type)
            report.display_name = f"{report.chat_id.title} - {type_name} - {period}"

    def action_view_chart(self):
        """Открывает аналитику для текущего отчёта"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Analytics',
            'res_model': 'chat.analysis.report',
            'view_mode': 'graph,pivot',
            'target': 'current',
            'context': {
                'default_chat_id': self.chat_id.id,
            },
        }

    def action_analyze(self):
        """Запуск period-based анализа через Celery"""
        self.ensure_one()

        if self.state == 'processing':
            raise UserError("Analysis is already in progress")

        if not self.date_start or not self.date_end:
            raise UserError("Please specify date range for analysis")

        if self.analysis_type == 'compliance' and not self.instruction:
            raise UserError("Instruction is required for compliance check")

        self.write({
            'state': 'processing',
            'analysis_started_at': fields.Datetime.now(),
        })

        try:
            if self.analysis_type == 'review':
                payload = {
                    'user_id': self.user_id.id,
                    'chat_id': self.chat_id.external_id,
                    'start_date': self.date_start.isoformat(),
                    'end_date': self.date_end.isoformat(),
                }
                endpoint = "analysis/review/by-period"
            else:
                payload = {
                    'user_id': self.user_id.id,
                    'chat_id': self.chat_id.external_id,
                    'instruction': self.instruction,
                    'instruction_domain': self.instruction_domain or "",
                    'start_date': self.date_start.isoformat(),
                    'end_date': self.date_end.isoformat(),
                }
                endpoint = "analysis/compliance/by-period"

            full_url = self._get_full_url(endpoint)

            response = requests.post(
                full_url,
                json=payload,
                headers=self._get_headers(),
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                self.task_id = result.get('task_id')
                self.message_post(
                    body=f"Analysis started successfully! Task ID: {self.task_id}",
                    subject="Analysis Started"
                )
            else:
                raise Exception(f"API returned {response.status_code}: {response.text}")

        except Exception as e:
            _logger.error(f"Failed to start analysis: {e}")
            self.write({
                'state': 'error',
                'error_message': str(e),
                'analysis_completed_at': fields.Datetime.now(),
            })
            raise UserError(f"Failed to start analysis: {str(e)}")

    def action_refresh_status(self):
        """Обновление статуса из Celery"""
        self.ensure_one()

        if not self.task_id:
            raise UserError("No task ID found for this report")

        try:
            # Используем _get_full_url для правильного формирования URL
            full_url = self._get_full_url(f"analysis/task/{self.task_id}")

            _logger.info(f"Refreshing status from: {full_url}")

            response = requests.get(
                full_url,
                headers=self._get_headers(),
                timeout=10
            )

            if response.status_code == 200:
                task_data = response.json()
                _logger.info(f"Task data: {task_data}")

                if task_data['status'] == 'completed':
                    self._update_from_result(task_data.get('result', {}))
                    self.write({
                        'state': 'completed',
                        'analysis_completed_at': fields.Datetime.now(),
                    })
                    if self.analysis_started_at:
                        duration = (self.analysis_completed_at - self.analysis_started_at).total_seconds()
                        self.analysis_duration = duration

                    self.message_post(
                        body="Analysis completed successfully!",
                        subject="Analysis Complete"
                    )

                elif task_data['status'] == 'failed':
                    self.write({
                        'state': 'error',
                        'error_message': task_data.get('error', 'Unknown error'),
                        'analysis_completed_at': fields.Datetime.now(),
                    })

                    self.message_post(
                        body=f"Analysis failed: {self.error_message}",
                        subject="Analysis Failed",
                        message_type='notification'
                    )
                elif task_data['status'] == 'processing':
                    # Обновляем прогресс если есть
                    if task_data.get('progress'):
                        self.write({'progress': task_data['progress']})

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Status Updated',
                        'message': f'Task status: {task_data["status"]}',
                        'type': 'info',
                        'sticky': False,
                    }
                }
            else:
                raise Exception(f"API returned {response.status_code}: {response.text}")

        except Exception as e:
            _logger.error(f"Failed to refresh status: {e}")
            raise UserError(f"Failed to refresh status: {str(e)}")

    def _update_from_result(self, result):
        """Обновление отчета из результата API"""
        if self.analysis_type == 'review':
            self.write({
                'summary': result.get('summary', ''),
                'sentiment': result.get('sentiment', 'neutral'),
                'key_points': '\n'.join(result.get('key_points', [])),
                'participant_count': result.get('participant_count', 0),
                'message_count': result.get('message_count', 0),
                'communication_style': result.get('communication_style', ''),
                'recommendations': '\n'.join(result.get('recommendations', [])),
            })
        else:  # compliance
            violations_list = result.get('violations', [])
            severe = [v for v in violations_list if v.get('severity') == 'severe']
            minor = [v for v in violations_list if v.get('severity') == 'minor']

            self.write({
                'compliant': result.get('compliant', False),
                'confidence': result.get('confidence', 0.0),
                'explanation': result.get('explanation', ''),
                'violations': '\n'.join([f"- {v.get('description', v)}" for v in violations_list]),
                'suggestions': '\n'.join(result.get('suggestions', [])),
                'severe_violations': len(severe),
                'minor_violations': len(minor),
            })

            if not result.get('compliant') and len(severe) > 0:
                self._create_ticket_from_violations(violations_list)

    def _create_ticket_from_violations(self, violations):
        """Создаёт задачу на основе нарушений"""
        try:
            ticket = self.env['chat.analysis.ticket'].create({
                'name': f"Violation in {self.chat_id.title}",
                'report_id': self.id,
                'chat_id': self.chat_id.id,
                'description': self.explanation,
                'violations': '\n'.join([v.get('description', str(v)) for v in violations]),
                'priority': 'high' if self.severe_violations > 0 else 'normal',
            })

            self.message_post(
                body=f"Ticket created: <a href=# data-oe-model=chat.analysis.ticket data-oe-id={ticket.id}>{ticket.name}</a>",
                subject="Ticket Created"
            )
            return ticket
        except Exception as e:
            _logger.error(f"Failed to create ticket: {e}")
            return None

    def action_retry(self):
        """Повторить отчёт"""
        self.ensure_one()
        if self.state != 'error':
            raise UserError("Only failed analyses can be retried")

        self.write({
            'state': 'pending',
            'error_message': False,
            'task_id': False,
            'analysis_completed_at': False,
            'analysis_started_at': False,
        })

        return self.action_analyze()

    def _get_api_url(self):
        """Получает URL API из настроек"""
        config = self.env['ir.config_parameter'].sudo()
        base_url = config.get_param('chat_analysis.api_url', 'http://chat_api:8000')
        return base_url.rstrip('/')

    def _get_full_url(self, endpoint):
        """Получает полный URL для API запроса"""
        api_url = self._get_api_url()
        endpoint = endpoint.lstrip('/')
        return f"{api_url}/api/v1/{endpoint}"

    def _get_api_key(self):
        """Получает API key из настроек"""
        config = self.env['ir.config_parameter'].sudo()
        return config.get_param('chat_analysis.api_key', 'odoo_api_key_1')

    def _get_headers(self):
        """Получает заголовки для API запроса"""
        return {
            'Authorization': f'Bearer {self._get_api_key()}',
            'Content-Type': 'application/json'
        }

    def action_export_report(self):
        """Экспорт отчёта в HTML"""
        self.ensure_one()

        if self.state != 'completed':
            raise UserError("Report must be completed before exporting")

        if self.analysis_type == 'review':
            content = self._generate_review_html()
        else:
            content = self._generate_compliance_html()

        attachment = self.env['ir.attachment'].create({
            'name': f'report_{self.id}_{self.create_date.strftime("%Y%m%d_%H%M%S")}.html',
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

    def _generate_review_html(self):
        """Генерация HTML для review отчёта"""
        period = f"{self.date_start.strftime('%Y-%m-%d %H:%M')} - {self.date_end.strftime('%Y-%m-%d %H:%M')}"

        return f"""
        <html>
        <head><meta charset="utf-8"><title>Review Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            h1 {{ color: #2c3e50; }}
            .header {{ background: #3498db; color: white; padding: 20px; border-radius: 5px; }}
            .section {{ margin: 20px 0; padding: 15px; background: #f9f9f9; border-radius: 5px; }}
            .sentiment-positive {{ color: #27ae60; font-weight: bold; }}
            .sentiment-neutral {{ color: #f39c12; font-weight: bold; }}
            .sentiment-negative {{ color: #e74c3c; font-weight: bold; }}
        </style>
        </head>
        <body>
            <div class="header">
                <h1>Review Report</h1>
                <p><strong>Chat:</strong> {self.chat_id.title}</p>
                <p><strong>Period:</strong> {period}</p>
                <p><strong>Generated:</strong> {fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            <div class="section">
                <h2>Summary</h2>
                <p>{self.summary or 'No summary'}</p>
            </div>
            <div class="section">
                <h2>Sentiment</h2>
                <p class="sentiment-{self.sentiment}">{self.sentiment or 'Unknown'}</p>
            </div>
            <div class="section">
                <h2>Key Points</h2>
                <p>{self.key_points or 'No key points'}</p>
            </div>
            <div class="section">
                <h2>Statistics</h2>
                <ul>
                    <li>Participants: {self.participant_count or 0}</li>
                    <li>Messages: {self.message_count or 0}</li>
                    <li>Communication Style: {self.communication_style or 'N/A'}</li>
                </ul>
            </div>
            <div class="section">
                <h2>Recommendations</h2>
                <p>{self.recommendations or 'No recommendations'}</p>
            </div>
        </body>
        </html>
        """

    def _generate_compliance_html(self):
        """Генерация HTML для compliance отчёта"""
        period = f"{self.date_start.strftime('%Y-%m-%d %H:%M')} - {self.date_end.strftime('%Y-%m-%d %H:%M')}"
        status_color = '#27ae60' if self.compliant else '#e74c3c'
        status_text = 'COMPLIANT' if self.compliant else 'NON-COMPLIANT'

        return f"""
        <html>
        <head><meta charset="utf-8"><title>Compliance Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            h1 {{ color: #2c3e50; }}
            .header {{ background: {status_color}; color: white; padding: 20px; border-radius: 5px; }}
            .section {{ margin: 20px 0; padding: 15px; background: #f9f9f9; border-radius: 5px; }}
            .violation {{ color: #e74c3c; }}
            .suggestion {{ color: #27ae60; }}
        </style>
        </head>
        <body>
            <div class="header">
                <h1>Compliance Report</h1>
                <p><strong>Status:</strong> {status_text}</p>
                <p><strong>Chat:</strong> {self.chat_id.title}</p>
                <p><strong>Period:</strong> {period}</p>
                <p><strong>Generated:</strong> {fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            <div class="section">
                <h2>Compliance Details</h2>
                <p><strong>Confidence:</strong> {(self.confidence or 0) * 100:.1f}%</p>
                <p><strong>Severe Violations:</strong> {self.severe_violations or 0}</p>
                <p><strong>Minor Violations:</strong> {self.minor_violations or 0}</p>
            </div>
            <div class="section">
                <h2>Instruction</h2>
                <p>{self.instruction or 'No instruction provided'}</p>
                {f'<p><strong>Domain:</strong> {self.instruction_domain}</p>' if self.instruction_domain else ''}
            </div>
            <div class="section">
                <h2>Explanation</h2>
                <p>{self.explanation or 'No explanation available'}</p>
            </div>
            <div class="section">
                <h2>Violations</h2>
                <p class="violation">{self.violations or 'No violations identified'}</p>
            </div>
            <div class="section">
                <h2>Suggestions</h2>
                <p class="suggestion">{self.suggestions or 'No suggestions'}</p>
            </div>
        </body>
        </html>
        """


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
        ('urgent', 'Urgent')
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
                'title': 'Success',
                'message': 'Ticket reopened',
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
