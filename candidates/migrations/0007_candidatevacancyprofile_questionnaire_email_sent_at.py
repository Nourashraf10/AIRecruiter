# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('candidates', '0006_candidatevacancyprofile_recommendation_email_sent_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='candidatevacancyprofile',
            name='questionnaire_email_sent_at',
            field=models.DateTimeField(blank=True, help_text='When questionnaire email was last sent (avoid duplicate sends)', null=True),
        ),
    ]
