from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("tickets", "0006_correct_tickets_functions"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                DROP VIEW IF EXISTS user_tickets_view;  -- <== DODANA LINIA

                CREATE VIEW user_tickets_view AS        -- <== ZMIANA z 'CREATE OR REPLACE' na 'CREATE'
                SELECT
                    o.id AS order_id,
                    o.user_id,
                    o.status AS order_status,
                    o.updated_at,
                    od."ticket_UUID",
                    t.event_id,
                    t.seat,
                    t.status AS ticket_status
                FROM orders o
                JOIN orders_details od ON o.id = od.order_id
                JOIN tickets t ON od.ticket_id = t.id
                WHERE o.status = 'completed';
            """,
            reverse_sql="DROP VIEW IF EXISTS user_tickets_view;",
        )
    ]