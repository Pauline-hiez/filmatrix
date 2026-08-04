"""Instance centrale de SQLAlchemy, importée par les autres modules"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()