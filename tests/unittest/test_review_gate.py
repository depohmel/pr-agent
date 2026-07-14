import unittest
from unittest.mock import Mock, patch

from pr_agent.tools.pr_reviewer import PRReviewer


class TestReviewGate(unittest.TestCase):

    def setUp(self):
        # Create a PRReviewer instance with minimal required arguments
        # We'll mock the git_provider and other dependencies
        self.pr_reviewer = PRReviewer(pr_url="https://github.com/user/repo/pull/1")
        # Mock the git_provider to avoid actual API calls
        self.pr_reviewer.git_provider = Mock()

    @patch('pr_agent.tools.pr_reviewer.get_settings')
    def test_gate_disabled(self, mock_get_settings):
        # When gate is disabled, should return (None, None)
        mock_settings = Mock()
        mock_settings.pr_reviewer.get.return_value = False
        mock_get_settings.return_value = mock_settings

        event, body = self.pr_reviewer._get_review_gate_decision()
        self.assertIsNone(event)
        self.assertIsNone(body)

    @patch('pr_agent.tools.pr_reviewer.get_settings')
    def test_gate_enabled_clean_verdict(self, mock_get_settings):
        # When gate is enabled and review is clean (no key_issues, no security concerns)
        mock_settings = Mock()
        mock_settings.pr_reviewer.get.return_value = True
        mock_get_settings.return_value = mock_settings

        # Set up parsed_review_data with clean review
        self.pr_reviewer.parsed_review_data = {
            'review': {
                'key_issues_to_review': [],
                'security_concerns': 'no'
            }
        }

        event, body = self.pr_reviewer._get_review_gate_decision()
        self.assertEqual(event, "APPROVE")
        self.assertIsNone(body)

    @patch('pr_agent.tools.pr_reviewer.get_settings')
    def test_gate_enabled_with_key_issues(self, mock_get_settings):
        # When gate is enabled and review has key_issues
        mock_settings = Mock()
        mock_settings.pr_reviewer.get.return_value = True
        mock_get_settings.return_value = mock_settings

        # Set up parsed_review_data with key_issues
        self.pr_reviewer.parsed_review_data = {
            'review': {
                'key_issues_to_review': [
                    "Issue 1: Something is wrong",
                    "Issue 2: Another thing is wrong"
                ],
                'security_concerns': 'no'
            }
        }

        event, body = self.pr_reviewer._get_review_gate_decision()
        self.assertEqual(event, "REQUEST_CHANGES")
        self.assertIsNotNone(body)
        self.assertIn("### Key Issues Found", body)
        self.assertIn("- Issue 1: Something is wrong", body)
        self.assertIn("- Issue 2: Another thing is wrong", body)
        self.assertNotIn("### Security Concern", body)

    @patch('pr_agent.tools.pr_reviewer.get_settings')
    def test_gate_enabled_with_security_concern(self, mock_get_settings):
        # When gate is enabled and review has security concern
        mock_settings = Mock()
        mock_settings.pr_reviewer.get.return_value = True
        mock_get_settings.return_value = mock_settings

        # Set up parsed_review_data with security concern
        self.pr_reviewer.parsed_review_data = {
            'review': {
                'key_issues_to_review': [],
                'security_concerns': 'yes'
            }
        }

        event, body = self.pr_reviewer._get_review_gate_decision()
        self.assertEqual(event, "REQUEST_CHANGES")
        self.assertIsNotNone(body)
        self.assertIn("### Security Concern", body)
        self.assertIn("The review flagged a possible security concern that needs to be addressed.", body)
        self.assertNotIn("### Key Issues Found", body)

    @patch('pr_agent.tools.pr_reviewer.get_settings')
    def test_gate_enabled_with_both_key_issues_and_security_concern(self, mock_get_settings):
        # When gate is enabled and review has both key_issues and security concerns
        mock_settings = Mock()
        mock_settings.pr_reviewer.get.return_value = True
        mock_get_settings.return_value = mock_settings

        # Set up parsed_review_data with both
        self.pr_reviewer.parsed_review_data = {
            'review': {
                'key_issues_to_review': [
                    "Issue 1: Something is wrong"
                ],
                'security_concerns': 'yes'
            }
        }

        event, body = self.pr_reviewer._get_review_gate_decision()
        self.assertEqual(event, "REQUEST_CHANGES")
        self.assertIsNotNone(body)
        self.assertIn("### Key Issues Found", body)
        self.assertIn("- Issue 1: Something is wrong", body)
        self.assertIn("### Security Concern", body)
        self.assertIn("The review flagged a possible security concern that needs to be addressed.", body)


if __name__ == '__main__':
    unittest.main()