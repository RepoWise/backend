"""
Enhanced Governance File Pattern Matcher
Comprehensive pattern matching for all governance document types across any location
"""
import os
import re
from typing import Optional, Tuple, List
from dataclasses import dataclass


@dataclass
class GovernancePattern:
    """Represents a governance file pattern"""
    category: str
    filenames: List[str]
    extensions: List[str]
    locations: List[str]


class GovernancePatternMatcher:
    """
    Comprehensive pattern matching for governance files
    Handles all variations: case, extensions, directories, etc.
    """

    # Comprehensive governance file patterns
    PATTERNS = {
        'governance': GovernancePattern(
            category='governance',
            filenames=['governance', 'project-governance'],
            extensions=['.md', '.txt', '.rst', ''],
            locations=['', '.github/', 'docs/', 'community/', '.gitlab/']
        ),
        'contributing': GovernancePattern(
            category='contributing',
            filenames=['contributing', 'contribute', 'contribution'],
            extensions=['.md', '.txt', '.rst', ''],
            locations=['', '.github/', 'docs/', 'community/', '.gitlab/', 'templates/']
        ),
        'code_of_conduct': GovernancePattern(
            category='code_of_conduct',
            filenames=['code_of_conduct', 'code-of-conduct', 'coc', 'conduct'],
            extensions=['.md', '.txt', '.rst', ''],
            locations=['', '.github/', 'docs/', 'community/', '.gitlab/']
        ),
        'security': GovernancePattern(
            category='security',
            filenames=['security', 'security-policy', 'security_policy'],
            extensions=['.md', '.txt', '.rst', ''],
            locations=['', '.github/', 'docs/', '.gitlab/']
        ),
        'maintainers': GovernancePattern(
            category='maintainers',
            filenames=['maintainers', 'codeowners', 'owners', 'committers', 'team'],
            extensions=['.md', '.txt', ''],
            locations=['', '.github/', 'docs/', 'community/', '.gitlab/']
        ),
        'license': GovernancePattern(
            category='license',
            filenames=['license', 'licence', 'copying', 'notice'],
            extensions=['.md', '.txt', ''],
            locations=['', 'docs/']
        ),
        'charter': GovernancePattern(
            category='charter',
            filenames=['charter', 'project-charter'],
            extensions=['.md', '.txt', '.rst', ''],
            locations=['', '.github/', 'docs/', 'community/']
        ),
        'readme': GovernancePattern(
            category='readme',
            filenames=['readme'],
            extensions=['.md', '.txt', '.rst', ''],
            locations=['', 'docs/']
        ),
        'support': GovernancePattern(
            category='support',
            filenames=['support', 'getting-help', 'help'],
            extensions=['.md', '.txt', '.rst', ''],
            locations=['', '.github/', 'docs/', '.gitlab/']
        ),
        'roadmap': GovernancePattern(
            category='roadmap',
            filenames=['roadmap', 'project-roadmap'],
            extensions=['.md', '.txt', '.rst', ''],
            locations=['', 'docs/', 'community/']
        ),
        'changelog': GovernancePattern(
            category='changelog',
            filenames=['changelog', 'changes', 'history', 'releases', 'news'],
            extensions=['.md', '.txt', '.rst', ''],
            locations=['', 'docs/']
        ),
        'authors': GovernancePattern(
            category='authors',
            filenames=['authors', 'contributors', 'credits'],
            extensions=['.md', '.txt', ''],
            locations=['', 'docs/']
        ),
        'funding': GovernancePattern(
            category='funding',
            filenames=['funding'],
            extensions=['.yml', '.yaml', '.md', ''],
            locations=['.github/']
        )
    }

    # Additional keywords for governance directories
    GOVERNANCE_KEYWORDS = [
        'governance', 'contributing', 'conduct', 'security',
        'maintainer', 'owner', 'committer', 'charter',
        'policy', 'guideline', 'coc'
    ]

    # Governance-related directories
    GOVERNANCE_DIRS = [
        '.github', 'docs', 'community', '.gitlab',
        'governance', 'policies', 'templates'
    ]

    def matches(self, filepath: str) -> Tuple[bool, Optional[str]]:
        """
        Check if filepath is a governance file

        Args:
            filepath: Relative path from repo root

        Returns:
            (is_governance_file, category)
        """
        path_lower = filepath.lower()
        filename = os.path.basename(path_lower)
        dirname = os.path.dirname(path_lower)

        # Method 1: Exact pattern matching
        for category, pattern in self.PATTERNS.items():
            if self._matches_pattern(filename, dirname, pattern):
                return True, category

        # Method 2: Template files in .github
        if self._is_template_file(path_lower):
            return True, 'templates'

        # Method 3: Governance directories with relevant keywords
        if self._is_governance_dir_file(path_lower, filename):
            return True, 'governance'

        return False, None

    def _matches_pattern(
        self,
        filename: str,
        dirname: str,
        pattern: GovernancePattern
    ) -> bool:
        """Check if file matches a specific pattern"""
        # Check all combinations of base name + extension
        for base in pattern.filenames:
            for ext in pattern.extensions:
                expected = f"{base}{ext}"

                # Check in all possible locations
                for location in pattern.locations:
                    # Root location
                    if not location and dirname == '' and filename == expected:
                        return True

                    # Specific directory
                    if location:
                        # Remove trailing slash for comparison
                        loc = location.rstrip('/')
                        if dirname == loc and filename == expected:
                            return True
                        # Also check subdirectories (e.g., docs/governance/)
                        if dirname.startswith(loc + '/') and filename == expected:
                            return True

        return False

    def _is_template_file(self, path: str) -> bool:
        """Check if file is a template (issue/PR templates, etc.)"""
        if '.github' not in path:
            return False

        template_indicators = [
            'issue_template', 'pull_request_template',
            'bug_report', 'feature_request', 'config.yml'
        ]

        return any(indicator in path for indicator in template_indicators)

    def _is_governance_dir_file(self, path: str, filename: str) -> bool:
        """Check if file is in a governance directory with relevant keywords"""
        # Check if in a governance directory
        in_gov_dir = any(gov_dir in path for gov_dir in self.GOVERNANCE_DIRS)

        if not in_gov_dir:
            return False

        # Check if filename contains governance keywords
        return any(keyword in filename for keyword in self.GOVERNANCE_KEYWORDS)

    def get_all_possible_paths(self) -> List[str]:
        """
        Generate all possible governance file paths
        Used for targeted Contents API queries

        Returns:
            List of paths to check
        """
        paths = []

        for pattern in self.PATTERNS.values():
            for base in pattern.filenames:
                for ext in pattern.extensions:
                    filename = f"{base}{ext}"

                    for location in pattern.locations:
                        if location:
                            paths.append(f"{location}{filename}")
                        else:
                            paths.append(filename)

        # Add common template paths
        template_paths = [
            '.github/ISSUE_TEMPLATE/bug_report.md',
            '.github/ISSUE_TEMPLATE/feature_request.md',
            '.github/ISSUE_TEMPLATE/config.yml',
            '.github/PULL_REQUEST_TEMPLATE.md',
            '.github/FUNDING.yml'
        ]
        paths.extend(template_paths)

        # Remove duplicates and sort
        return sorted(set(paths))

    def categorize_file(self, filepath: str) -> Optional[str]:
        """
        Get the category of a governance file

        Args:
            filepath: Path to categorize

        Returns:
            Category string or None
        """
        is_gov, category = self.matches(filepath)
        return category if is_gov else None

    def get_file_type_display_name(self, category: str) -> str:
        """Get human-readable display name for category"""
        display_names = {
            'governance': 'Governance',
            'contributing': 'Contributing',
            'code_of_conduct': 'Code of Conduct',
            'security': 'Security',
            'maintainers': 'Maintainers',
            'license': 'License',
            'charter': 'Charter',
            'readme': 'README',
            'support': 'Support',
            'roadmap': 'Roadmap',
            'changelog': 'Changelog',
            'authors': 'Authors',
            'funding': 'Funding',
            'templates': 'Templates'
        }
        return display_names.get(category, category.title())


# Global instance for easy access
pattern_matcher = GovernancePatternMatcher()


def is_governance_file(filepath: str) -> bool:
    """Convenience function to check if a file is a governance file"""
    is_gov, _ = pattern_matcher.matches(filepath)
    return is_gov


def get_governance_category(filepath: str) -> Optional[str]:
    """Convenience function to get governance file category"""
    return pattern_matcher.categorize_file(filepath)
