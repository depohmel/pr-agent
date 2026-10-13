import unittest
from unittest.mock import Mock, patch

from pr_agent.tools.pr_reviewer import PRReviewer


class TestReviewGate(unittest.TestCase):

    @patch('pr_agent.tools.pr_reviewer.get_git_provider_with_context')
    def setUp(self, mock_get_git_provider):
        # Create a mock git provider
        mock_git_provider = Mock()
        mock_git_provider.get_languages.return_value = {}
        mock_git_provider.get_files.return_value = []
        mock_git_provider.get_pr_branch.return_value = 'main'
        mock_git_provider.get_num_of_files.return_value = 1
        mock_git_provider.get_pr_title.return_value = 'Test PR'
        # When split_changes_walkthrough=True, get_pr_description returns (description, files)
        mock_git_provider.get_pr_description.return_value = ('Test description', [])
        mock_git_provider.get_commit_messages.return_value = ''
        mock_get_git_provider.return_value = mock_git_provider

        # Create a PRReviewer instance
        self.pr_reviewer = PRReviewer(pr_url="https://github.com/user/repo/pull/1")
        # The git_provider is now the mock because we patched get_git_provider_with_context

    @patch('pr_agent.tools.pr_reviewer.get_settings')
    def test_gate_disabled(self, mock_get_settings):
        # PR reviewer is disabled
        mock_settings = Mock()
        mock_settings.pr_reviewer.get.return_value = False
        mock_get_settings.return_value = mock_settings

        self.pr_reviewer.parsed_review_data = {
            'review': {
                'key_issues_to_review': [
                    {"relevant_file": "file.py", "issue_header": "Test", "issue_content": "content"},
                ],
                'security_concerns': 'no'
            }
        }

        event, body = self.pr_reviewer._get_review_gate_decision()
        self.assertIsNone(event)
        self.assertIsNone(body)

    @patch('pr_agent.tools.pr_reviewer.get_settings')
    def test_gate_enabled_clean_verdict(self, mock_get_settings):
        # No key issues and no security concerns
        mock_settings = Mock()
        mock_settings.pr_reviewer.get.return_value = True
        mock_get_settings.return_value = mock_settings

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
        # Has key issues
        mock_settings = Mock()
        mock_settings.pr_reviewer.get.return_value = True
        mock_get_settings.return_value = mock_settings

        self.pr_reviewer.parsed_review_data = {
            'review': {
                'key_issues_to_review': [
                    {
                        'relevant_file': 'file.py',
                        'issue_header': 'Test Header',
                        'issue_content': 'Test content'
                    }
                ],
                'security_concerns': 'no'
            }
        }

        event, body = self.pr_reviewer._get_review_gate_decision()
        self.assertEqual(event, "REQUEST_CHANGES")
        self.assertIsNotNone(body)
        self.assertIn("### Key Issues Found", body)
        self.assertIn("- **Test Header** (file.py): Test content", body)

    @patch('pr_agent.tools.pr_reviewer.get_settings')
    def test_gate_enabled_with_security_concern(self, mock_get_settings):
        # Has security concerns
        mock_settings = Mock()
        mock_settings.pr_reviewer.get.return_value = True
        mock_get_settings.return_value = mock_settings

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
        # Has both key issues and security concerns
        mock_settings = Mock()
        mock_settings.pr_reviewer.get.return_value = True
        mock_get_settings.return_value = mock_settings

        self.pr_reviewer.parsed_review_data = {
            'review': {
                'key_issues_to_review': [
                    {
                        'relevant_file': 'file.py',
                        'issue_header': 'Test Header',
                        'issue_content': 'Test content'
                    }
                ],
                'security_concerns': 'yes'
            }
        }

        event, body = self.pr_reviewer._get_review_gate_decision()
        self.assertEqual(event, "REQUEST_CHANGES")
        self.assertIsNotNone(body)
        self.assertIn("### Key Issues Found", body)
        self.assertIn("- **Test Header** (file.py): Test content", body)
        self.assertIn("### Security Concern", body)
        self.assertIn("The review flagged a possible security concern that needs to be addressed.", body)

    @patch('pr_agent.tools.pr_reviewer.get_settings')
    def test_gate_enabled_with_key_issues_as_empty_string(self, mock_get_settings):
        # key_issues as empty string
        mock_settings = Mock()
        mock_settings.pr_reviewer.get.return_value = True
        mock_get_settings.return_value = mock_settings

        self.pr_reviewer.parsed_review_data = {
            'review': {
                'key_issues_to_review': '',
                'security_concerns': 'no'
            }
        }

        event, body = self.pr_reviewer._get_review_gate_decision()
        self.assertEqual(event, "APPROVE")
        self.assertIsNone(body)

    @patch('pr_agent.tools.pr_reviewer.get_settings')
    def test_gate_enabled_with_key_issues_as_string_empty_brackets(self, mock_get_settings):
        # key_issues as "[]"
        mock_settings = Mock()
        mock_settings.pr_reviewer.get.return_value = True
        mock_get_settings.return_value = mock_settings

        self.pr_reviewer.parsed_review_data = {
            'review': {
                'key_issues_to_review': '[]',
                'security_concerns': 'no'
            }
        }

        event, body = self.pr_reviewer._get_review_gate_decision()
        self.assertEqual(event, "APPROVE")
        self.assertIsNone(body)

    @patch('pr_agent.tools.pr_reviewer.get_settings')
    def test_gate_enabled_with_key_issues_as_string_empty_braces(self, mock_get_settings):
        # key_issues as "{}"
        mock_settings = Mock()
        mock_settings.pr_reviewer.get.return_value = True
        mock_get_settings.return_value = mock_settings

        self.pr_reviewer.parsed_review_data = {
            'review': {
                'key_issues_to_review': '{}',
                'security_concerns': 'no'
            }
        }

        event, body = self.pr_reviewer._get_review_gate_decision()
        self.assertEqual(event, "APPROVE")
        self.assertIsNone(body)

    @patch('pr_agent.tools.pr_reviewer.get_settings')
    def test_gate_enabled_with_key_issues_as_none(self, mock_get_settings):
        # key_issues as None
        mock_settings = Mock()
        mock_settings.pr_reviewer.get.return_value = True
        mock_get_settings.return_value = mock_settings

        self.pr_reviewer.parsed_review_data = {
            'review': {
                'key_issues_to_review': None,
                'security_concerns': 'no'
            }
        }

        event, body = self.pr_reviewer._get_review_gate_decision()
        self.assertEqual(event, "APPROVE")
        self.assertIsNone(body)

    @patch('pr_agent.tools.pr_reviewer.get_settings')
    def test_gate_enabled_with_key_issues_as_list_of_dicts(self, mock_get_settings):
        # key_issues as a list of dicts (expected format)
        mock_settings = Mock()
        mock_settings.pr_reviewer.get.return_value = True
        mock_get_settings.return_value = mock_settings

        self.pr_reviewer.parsed_review_data = {
            'review': {
                'key_issues_to_review': [
                    {
                        'relevant_file': 'file.py',
                        'issue_header': 'Test Header',
                        'issue_content': 'Test content'
                    }
                ],
                'security_concerns': 'no'
            }
        }

        event, body = self.pr_reviewer._get_review_gate_decision()
        self.assertEqual(event, "REQUEST_CHANGES")
        self.assertIsNotNone(body)
        self.assertIn("### Key Issues Found", body)
        self.assertIn("- **Test Header** (file.py): Test content", body)
        self.assertNotIn(
            "- {'relevant_file': 'file.py', 'issue_header': 'Test Header', 'issue_content': 'Test content'}",
            body)
        self.assertNotIn("### Security Concern", body)

    @patch('pr_agent.tools.pr_reviewer.get_settings')
    def test_gate_enabled_with_key_issues_as_list_with_non_dict(self, mock_get_settings):
        # key_issues as a list containing a non-dict (e.g., a string)
        mock_settings = Mock()
        mock_settings.pr_reviewer.get.return_value = True
        mock_get_settings.return_value = mock_settings

        self.pr_reviewer.parsed_review_data = {
            'review': {
                'key_issues_to_review': [
                    "This is a string issue"
                ],
                'security_concerns': 'no'
            }
        }

        event, body = self.pr_reviewer._get_review_gate_decision()
        self.assertEqual(event, "REQUEST_CHANGES")
        self.assertIsNotNone(body)
        self.assertIn("### Key Issues Found", body)
        self.assertIn("- This is a string issue", body)
        self.assertNotIn("### Security Concern", body)

    @patch('pr_agent.tools.pr_reviewer.get_settings')
    def test_gate_enabled_with_security_concerns_yes_case_insensitive(self, mock_get_settings):
        # security_concerns as "Yes"
        mock_settings = Mock()
        mock_settings.pr_reviewer.get.return_value = True
        mock_get_settings.return_value = mock_settings

        self.pr_reviewer.parsed_review_data = {
            'review': {
                'key_issues_to_review': [],
                'security_concerns': 'Yes'
            }
        }

        event, body = self.pr_reviewer._get_review_gate_decision()
        self.assertEqual(event, "REQUEST_CHANGES")
        self.assertIsNotNone(body)
        self.assertIn("### Security Concern", body)
        self.assertIn("The review flagged a possible security concern that needs to be addressed.", body)
        self.assertNotIn("### Key Issues Found", body)

    @patch('pr_agent.tools.pr_reviewer.get_settings')
    def test_gate_enabled_with_security_concerns_as_none(self, mock_get_settings):
        # security_concerns as None
        mock_settings = Mock()
        mock_settings.pr_reviewer.get.return_value = True
        mock_get_settings.return_value = mock_settings

        self.pr_reviewer.parsed_review_data = {
            'review': {
                'key_issues_to_review': [],
                'security_concerns': None
            }
        }

        event, body = self.pr_reviewer._get_review_gate_decision()
        # None -> str(None) -> 'None', which does not contain 'yes' or 'true', so security_concerns_bool is False
        # Then if key_issues is empty, we get APPROVE
        self.assertEqual(event, "APPROVE")
        self.assertIsNone(body)

    @patch('pr_agent.tools.pr_reviewer.get_settings')
    def test_gate_enabled_with_security_concerns_as_dict_no_crash(self, mock_get_settings):
        # security_concerns as a dict (should not crash)
        mock_settings = Mock()
        mock_settings.pr_reviewer.get.return_value = True
        mock_get_settings.return_value = mock_settings

        self.pr_reviewer.parsed_review_data = {
            'review': {
                'key_issues_to_review': [],
                'security_concerns': {'some': 'dict'}
            }
        }

        # This should not raise an exception
        event, body = self.pr_reviewer._get_review_gate_decision()
        # The dict becomes "{'some': 'dict'}" which does not contain 'yes' or 'true' (unless the
        # string representation does by chance)
        # So we expect APPROVE if key_issues is empty.
        self.assertEqual(event, "APPROVE")
        self.assertIsNone(body)


if __name__ == '__main__':
    unittest.main()
