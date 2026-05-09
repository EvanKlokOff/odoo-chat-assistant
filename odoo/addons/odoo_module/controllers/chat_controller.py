from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class ChatAnalysisController(http.Controller):

    @http.route('/chat_analysis/dashboard_data', type='json', auth='user')
    def dashboard_data(self):
        """Получить данные для дашборда"""
        report_model = request.env['chat.analysis.report']

        return {
            'total_reports': report_model.search_count([]),
            'compliant_reports': report_model.search_count([('compliant', '=', True)]),
            'non_compliant_reports': report_model.search_count([('compliant', '=', False)]),
            'recent_reports': self._get_recent_reports(),
        }

    @http.route('/chat_analysis/chat_statistics/<int:chat_id>', type='json', auth='user')
    def chat_statistics(self, chat_id):
        """Получить статистику чата"""
        chat = request.env['chat.analysis.chat'].browse(chat_id)

        messages = request.env['chat.analysis.message'].search([
            ('chat_id', '=', chat.id)
        ], order='timestamp')

        return {
            'chat_name': chat.title,
            'total_messages': len(messages),
            'participants': len(messages.mapped('user_id')),
            'date_range': {
                'from': messages[0].timestamp if messages else None,
                'to': messages[-1].timestamp if messages else None,
            }
        }

    def _get_recent_reports(self, limit=5):
        """Получить последние отчёты"""
        reports = request.env['chat.analysis.report'].search([], order='create_date desc', limit=limit)
        return [{
            'id': r.id,
            'name': r.display_name,
            'type': r.analysis_type,
            'status': r.state,
            'create_date': r.create_date.strftime('%Y-%m-%d %H:%M'),
        } for r in reports]