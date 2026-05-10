from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class ChatAnalysisDashboard(models.Model):
    _name = 'chat.analysis.dashboard'
    _description = 'Chat Analysis Dashboard'

    chat_count = fields.Integer(string='Total Chats')
    user_count = fields.Integer(string='Total Users')
    message_count = fields.Integer(string='Total Messages')
    report_count = fields.Integer(string='Total Reports')
    compliant_count = fields.Integer(string='Compliant Reports')
    non_compliant_count = fields.Integer(string='Non-Compliant Reports')

    def init(self):
        """Инициализация отчёта"""
        pass

    def action_refresh_dashboard(self):
        """Обновляет данные дашборда и перезагружает форму"""
        # Пересчитываем данные для текущей записи
        for record in self:
            record.compute_data()

        # Возвращаем клиенту команду перезагрузить форму
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def compute_data(self):
        """Вычисление данных для дашборда"""
        self.chat_count = self.env['chat.analysis.chat'].search_count([])
        self.user_count = self.env['chat.analysis.user'].search_count([])
        self.message_count = self.env['chat.analysis.message'].search_count([])
        self.report_count = self.env['chat.analysis.report'].search_count([])
        self.compliant_count = self.env['chat.analysis.report'].search_count([
            ('compliant', '=', True)
        ])
        self.non_compliant_count = self.env['chat.analysis.report'].search_count([
            ('compliant', '=', False)
        ])

    def action_view_chart(self):
        """Открывает аналитику/графики для текущего отчёта"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Analytics',
            'res_model': 'chat.analysis.report',
            'view_mode': 'graph,pivot',  # Открываем график и сводную таблицу
            'res_id': self.id,  # Показываем текущую запись
            'target': 'current',  # В том же окне
            'context': {
                'search_default_group_by_type': 1,  # Можно добавить дефолтные фильтры
                'search_default_compliant': 1,
            },
        }


class ChatAnalysisStatistics(models.TransientModel):
    _name = 'chat.analysis.statistics'
    _description = 'Chat Statistics'

    chat_id = fields.Many2one('chat.analysis.chat', string='Chat')
    date_from = fields.Date(string='Date From')
    date_to = fields.Date(string='Date To')

    message_stats = fields.Text(string='Message Statistics', compute='_compute_stats')
    participant_stats = fields.Text(string='Participant Statistics', compute='_compute_stats')

    def action_refresh(self):
        """Пересчитывает статистику и перезагружает форму"""
        # Принудительно пересчитываем compute-поля
        self._compute_stats()

        # Возвращаем команду клиенту: перезагрузить текущую форму
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def _compute_stats(self):
        for record in self:
            stats = []

            domain = []
            if record.chat_id:
                domain.append(('chat_id', '=', record.chat_id.id))
            if record.date_from:
                domain.append(('timestamp', '>=', record.date_from))
            if record.date_to:
                domain.append(('timestamp', '<=', record.date_to))

            messages = self.env['chat.analysis.message'].search(domain, order='timestamp')

            if messages:
                stats.append(f"Total Messages: {len(messages)}")
                stats.append(f"Date Range: {messages[0].timestamp.date()} - {messages[-1].timestamp.date()}")

                # Статистика по пользователям
                users = messages.mapped('user_id')
                stats.append(f"Participants: {len(users)}")

                for user in users[:10]:
                    user_messages = messages.filtered(lambda m: m.user_id == user)
                    stats.append(f"  - {user.user_name}: {len(user_messages)} messages")

            record.message_stats = '\n'.join(stats) if stats else 'No data available'