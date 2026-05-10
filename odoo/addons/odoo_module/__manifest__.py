{
    'name': 'Chat Analysis Integration',
    'version': '18.0.1.0.0',
    'category': 'Tools',
    'summary': 'Integration with Telegram Chat Analysis Bot',
    'description': """
        Позволяет анализировать переписки из Telegram чатов.
        Возможности:
        - Синхронизация пользователей и чатов
        - Анализ переписки в определенный момент времени
        - Проверка соответствия переписки инструкции
        - Автоматическое создание задач при отклонениях
        - Дашборд с аналитикой по чатам
    """,
    'author': 'Your Company',
    'website': 'https://your-website.com',
    'depends': ['base', 'mail', 'contacts'],
    'data': [
        #'security/ir.model.access.csv',
        'wizards/chat_analysis_wizard_view.xml',
        'views/chat_analysis_views.xml',
        'views/chat_menu_views.xml',
        'views/chat_settings_views.xml',
        'views/chat_report_views.xml',
        'data/chat_cron_data.xml',
    ],
    'external_dependencies': {'python': ['requests']},
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'post_init_hook': 'post_init_hook',
}