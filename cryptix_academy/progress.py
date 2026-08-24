# cryptix_academy/progress.py

from cryptix_academy.models import LearningProgress
from utils.settings import load_settings, save_settings

class ProgressStore:
    @staticmethod
    def load_progress() -> LearningProgress:
        """
        Loads user progress from the local setting storage.
        If no progress exists, returns a fresh LearningProgress object.
        """
        settings = load_settings()
        profile_data = settings.get("learning_profile")

        if not profile_data:
            return LearningProgress()

        return LearningProgress(
            schema_version=profile_data.get("schema_version", 1),
            xp=profile_data.get("xp", 0),
            level=profile_data.get("level", 1),
            completed_lessons=profile_data.get("completed_lessons", []),
            completed_challenges=profile_data.get("completed_challenges", []),
            first_attempt_successes=profile_data.get("first_attempt_successes", 0),
            total_attempts=profile_data.get("total_attempts", 0)
        )

    @staticmethod
    def save_progress(progress: LearningProgress) -> None:
        """
        Saves user progress into the local setting storage.
        """
        settings = load_settings()
        settings["learning_profile"] = {
            "schema_version": progress.schema_version,
            "xp": progress.xp,
            "level": progress.level,
            "completed_lessons": list(progress.completed_lessons),
            "completed_challenges": list(progress.completed_challenges),
            "first_attempt_successes": progress.first_attempt_successes,
            "total_attempts": progress.total_attempts
        }
        save_settings(settings)

    @staticmethod
    def reset_progress() -> LearningProgress:
        """
        Wipes the stored learning profile completely and returns a fresh progress state.
        """
        settings = load_settings()
        if "learning_profile" in settings:
            del settings["learning_profile"]
            save_settings(settings)
        return LearningProgress()
