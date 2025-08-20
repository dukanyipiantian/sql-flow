from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class ParseHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sql_text = db.Column(db.Text)
    result_json = db.Column(db.JSON)
    created_at = db.Column(db.Datetime, default=db.func.now())