from enum import Enum


class UserRole(str, Enum):
    STUDENT = 'student'  # Aluno
    GUARDIAN = 'guardian'  # Responsável
    TEACHER = 'teacher'  # Professor
    COORDINATOR = 'coordinator'  # Coordenador
    PORTER = 'porter'  # Porteiro
    ADMIN = 'admin'  # Admin do sistema
