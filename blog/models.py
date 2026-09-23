from django.db import models
from django.utils import timezone


class Task(models.Model):
    STATUS_CHOICE = [('pending', 'Pending'), ('done', 'Done'), ('frozen', 'Frozen'), ('broken', 'Streak Broken')]

    name = models.CharField(max_length=100, unique=True)
    streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICE, default='pending')
    last_updated = models.DateTimeField(null=True, blank=True)
    freezes_left = models.IntegerField(default=3)
    last_freeze_reset = models.CharField(max_length=7, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.last_freeze_reset:
            self.last_freeze_reset = timezone.now().strftime("%Y-%m")
        super().save(*args, **kwargs)
