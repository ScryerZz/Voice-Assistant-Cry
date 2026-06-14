import unittest

from src.skills.ai_skill import AISkill


class FakeResponse:
    def __init__(self, status_code=400, message=""):
        self.status_code = status_code
        self.text = message
        self._message = message

    def json(self):
        return {"error": {"message": self._message}}


class AISkillTests(unittest.TestCase):
    def test_bad_request_folder_mismatch_is_actionable(self):
        skill = AISkill(api_key="test-key", folder_id="folder", enabled=True)
        response = FakeResponse(message="Specified folder ID 'folder' does not match with service account folder ID 'other'")

        message = skill._bad_request_message(response)

        self.assertIn("ID каталога", message)
        self.assertIn("не совпадает", message)

    def test_bad_request_unknown_is_not_generic_retry_later(self):
        skill = AISkill(api_key="test-key", folder_id="folder", enabled=True)
        response = FakeResponse(message="invalid request")

        message = skill._bad_request_message(response)

        self.assertIn("отклонил запрос", message)
        self.assertNotIn("Попробуйте позже", message)


if __name__ == "__main__":
    unittest.main()
