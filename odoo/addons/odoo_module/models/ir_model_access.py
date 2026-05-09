# models/ir_model_access.py
from odoo import api, models, SUPERUSER_ID


class IrModelAccess(models.Model):
    _inherit = 'ir.model.access'

    @api.model
    def _add_chat_analysis_access_rights(self):
        """Add access rights for chat analysis models"""
        models_to_configure = [
            ('chat.analysis.user', 'base.group_user', 1, 1, 1, 1),
            ('chat.analysis.chat', 'base.group_user', 1, 1, 1, 1),
            ('chat.analysis.report', 'base.group_user', 1, 1, 1, 1),
            ('chat.analysis.message', 'base.group_user', 1, 1, 1, 1),
            ('chat.analysis.ticket', 'base.group_user', 1, 1, 1, 1),
            ('chat.analysis.wizard', 'base.group_user', 1, 1, 1, 1),
            ('chat.sync.batch.wizard', 'base.group_user', 1, 1, 1, 1),
        ]

        for model_name, group_id, perm_read, perm_write, perm_create, perm_unlink in models_to_configure:
            model = self.env['ir.model'].search([('model', '=', model_name)], limit=1)
            if model:
                group = self.env.ref(group_id)
                existing = self.search([
                    ('model_id', '=', model.id),
                    ('group_id', '=', group.id)
                ], limit=1)

                if not existing:
                    self.create({
                        'name': f'access_{model_name.replace(".", "_")}',
                        'model_id': model.id,
                        'group_id': group.id,
                        'perm_read': perm_read,
                        'perm_write': perm_write,
                        'perm_create': perm_create,
                        'perm_unlink': perm_unlink,
                    })