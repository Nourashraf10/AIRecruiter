from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('candidates', '0007_candidatevacancyprofile_questionnaire_email_sent_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='BlueCollarLead',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=200)),
                ('phone', models.CharField(max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('vacancy', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='blue_collar_leads', to='vacancies.vacancy')),
            ],
            options={
                'verbose_name': 'Blue Collar Lead',
                'verbose_name_plural': 'Blue Collar Leads',
                'ordering': ['-created_at'],
            },
        ),
    ]

