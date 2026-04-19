from django.contrib import admin
from instructions.models import Instruction


@admin.register(Instruction)
class InstructionAdmin(admin.ModelAdmin):
    list_display = ["recipe", "step_number", "text"]
    list_filter = ["recipe"]
    ordering = ["recipe", "step_number"]
