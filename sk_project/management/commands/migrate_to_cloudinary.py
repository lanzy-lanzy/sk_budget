from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage
from django.core.files import File
from sk_project.models import Project, AccomplishmentReportImage, User  # Import your models that have media fields
import os

class Command(BaseCommand):
    help = 'Migrate existing media files to Cloudinary'

    def handle(self, *args, **kwargs):
        self.stdout.write('Starting media migration to Cloudinary...')

        # Migrate Project final_images
        projects = Project.objects.all()
        for project in projects:
            if project.final_image and os.path.exists(project.final_image.path):
                with open(project.final_image.path, 'rb') as f:
                    project.final_image = File(f)
                    project.save()
                self.stdout.write(f'Migrated final image for project: {project.name}')

        # Migrate AccomplishmentReportImage images
        report_images = AccomplishmentReportImage.objects.all()
        for report_image in report_images:
            if report_image.image and os.path.exists(report_image.image.path):
                with open(report_image.image.path, 'rb') as f:
                    report_image.image = File(f)
                    report_image.save()
                self.stdout.write(f'Migrated report image: {report_image.id}')

        # Migrate User profile pictures
        users = User.objects.all()
        for user in users:
            if user.profile_picture and os.path.exists(user.profile_picture.path):
                with open(user.profile_picture.path, 'rb') as f:
                    user.profile_picture = File(f)
                    user.save()
                self.stdout.write(f'Migrated profile picture for user: {user.username}')

        self.stdout.write(self.style.SUCCESS('Successfully migrated all media files to Cloudinary'))
