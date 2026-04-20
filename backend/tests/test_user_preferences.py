from app.infrastructure.persistence.postgres.models import UserPreferencesModel


def test_user_preferences_model_importable():
    assert UserPreferencesModel.__tablename__ == "user_preferences"
