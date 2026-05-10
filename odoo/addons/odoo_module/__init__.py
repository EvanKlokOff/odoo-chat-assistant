from . import models
from . import wizards

def post_init_hook(env): # В Odoo 18 передается только env
    """Post-install hook to add access rights"""

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
        model = env['ir.model'].search([('model', '=', model_name)], limit=1)
        if model:
            group = env.ref(group_id)
            existing = env['ir.model.access'].search([
                ('model_id', '=', model.id),
                ('group_id', '=', group.id)
            ], limit=1)

            if not existing:
                env['ir.model.access'].create({
                    'name': f'access_{model_name.replace(".", "_")}',
                    'model_id': model.id,
                    'group_id': group.id,
                    'perm_read': perm_read,
                    'perm_write': perm_write,
                    'perm_create': perm_create,
                    'perm_unlink': perm_unlink,
                })
