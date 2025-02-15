from sqlalchemy.orm import Session
from . import models, schemas

def create_feedback(db: Session, feedback: schemas.FeedbackCreate):
    db_feedback = models.Feedback(feedback=feedback.feedback)
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    return db_feedback
