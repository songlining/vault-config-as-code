"""
Git Handler Service

Handles Git operations for SCIM Bridge including repository cloning,
branch creation, commits, and GitHub PR creation for automated
identity provisioning workflows.
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import List, Optional

import requests


class GitHandler:
    """
    Git operations handler for SCIM Bridge.
    
    Manages repository cloning/updating, branch creation, committing changes,
    and creating GitHub pull requests for identity YAML file changes.
    """

    def __init__(self, repo_url: str, github_token: str):
        """
        Initialize GitHandler with repository URL and GitHub token.
        
        Args:
            repo_url: Git repository URL (e.g., 'https://github.com/user/repo.git')
            github_token: GitHub personal access token with repo permissions
        """
        self.repo_url = repo_url
        self.github_token = github_token
        self.clone_dir: Optional[Path] = None
        
        # Extract owner and repo name from URL for GitHub API
        if 'github.com' in repo_url:
            # Handle both SSH and HTTPS URLs
            if repo_url.startswith('git@github.com:'):
                # SSH format: git@github.com:owner/repo.git
                path_part = repo_url.replace('git@github.com:', '').replace('.git', '')
            else:
                # HTTPS format: https://github.com/owner/repo.git
                path_part = repo_url.replace('https://github.com/', '').replace('.git', '')
            
            self.owner, self.repo_name = path_part.split('/')
        else:
            raise ValueError("Only GitHub repositories are currently supported")

    def clone_or_pull(self, clone_dir: str) -> str:
        """
        Clone repository or update if it already exists.
        
        Args:
            clone_dir: Directory path to clone/update repository
            
        Returns:
            Path to the cloned/updated repository
            
        Raises:
            subprocess.CalledProcessError: If git operations fail
        """
        clone_path = Path(clone_dir)
        self.clone_dir = clone_path
        
        # Create parent directory if it doesn't exist
        clone_path.parent.mkdir(parents=True, exist_ok=True)
        
        if clone_path.exists() and (clone_path / '.git').exists():
            # Repository exists, pull latest changes
            self._run_git_command(['git', 'pull', 'origin', 'main'], cwd=clone_path)
            print(f"Updated existing repository at {clone_path}")
        else:
            # Clone repository
            # Remove directory if it exists but isn't a git repo
            if clone_path.exists():
                import shutil
                shutil.rmtree(clone_path)
            
            # Use token authentication for HTTPS URLs
            if self.repo_url.startswith('https://'):
                auth_url = self.repo_url.replace(
                    'https://', 
                    f'https://{self.github_token}@'
                )
            else:
                auth_url = self.repo_url
            
            self._run_git_command(['git', 'clone', auth_url, str(clone_path)])
            print(f"Cloned repository to {clone_path}")
        
        return str(clone_path)

    def create_pr_for_user(
        self, 
        username: str, 
        yaml_filename: str, 
        yaml_content: str,
        commit_message: Optional[str] = None
    ) -> str:
        """
        Create a PR for a new/updated user YAML file.
        
        Args:
            username: Username for branch naming (sanitized)
            yaml_filename: Name of the YAML file (e.g., 'entraid_human_jane_doe.yaml')
            yaml_content: Content of the YAML file
            commit_message: Optional commit message, auto-generated if None
            
        Returns:
            GitHub PR URL
        """
        if not self.clone_dir:
            raise ValueError("Repository must be cloned first using clone_or_pull()")
        
        # Generate timestamp for unique branch names
        timestamp = str(int(time.time()))
        branch_name = f"scim-provision-{username}-{timestamp}"
        
        # Generate commit message if not provided
        if commit_message is None:
            commit_message = f"SCIM: Add/update user identity for {username}"
        
        # Create and switch to new branch
        self._run_git_command(['git', 'checkout', 'main'], cwd=self.clone_dir)
        self._run_git_command(['git', 'pull', 'origin', 'main'], cwd=self.clone_dir)
        self._run_git_command(['git', 'checkout', '-b', branch_name], cwd=self.clone_dir)
        
        # Write YAML file
        yaml_path = self.clone_dir / 'identities' / yaml_filename
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        yaml_path.write_text(yaml_content, encoding='utf-8')
        
        # Stage and commit changes
        self._run_git_command(['git', 'add', f'identities/{yaml_filename}'], cwd=self.clone_dir)
        self._run_git_command(['git', 'commit', '-m', commit_message], cwd=self.clone_dir)
        
        # Push branch to remote
        self._run_git_command(['git', 'push', 'origin', branch_name], cwd=self.clone_dir)
        
        # Create GitHub PR
        pr_title = f"SCIM Provisioning: {username}"
        pr_body = self._generate_user_pr_body(username, yaml_filename, yaml_content)
        
        pr_url = self._create_github_pr(
            branch_name=branch_name,
            title=pr_title,
            body=pr_body,
            labels=['scim-provisioning', 'needs-review']
        )
        
        return pr_url

    def create_pr_for_groups(
        self, 
        username: str, 
        modified_files: List[str],
        commit_message: Optional[str] = None
    ) -> str:
        """
        Create a PR for group membership changes.
        
        Args:
            username: Username for branch naming and PR context
            modified_files: List of group file paths that were modified
            commit_message: Optional commit message, auto-generated if None
            
        Returns:
            GitHub PR URL
        """
        if not self.clone_dir:
            raise ValueError("Repository must be cloned first using clone_or_pull()")
        
        if not modified_files:
            raise ValueError("No modified files provided")
        
        # Generate timestamp for unique branch names
        timestamp = str(int(time.time()))
        branch_name = f"scim-provision-{username}-groups-{timestamp}"
        
        # Generate commit message if not provided
        if commit_message is None:
            commit_message = f"SCIM: Update group memberships for {username}"
        
        # Create and switch to new branch
        self._run_git_command(['git', 'checkout', 'main'], cwd=self.clone_dir)
        self._run_git_command(['git', 'pull', 'origin', 'main'], cwd=self.clone_dir)
        self._run_git_command(['git', 'checkout', '-b', branch_name], cwd=self.clone_dir)
        
        # Stage modified files
        for file_path in modified_files:
            self._run_git_command(['git', 'add', file_path], cwd=self.clone_dir)
        
        # Commit changes
        self._run_git_command(['git', 'commit', '-m', commit_message], cwd=self.clone_dir)
        
        # Push branch to remote
        self._run_git_command(['git', 'push', 'origin', branch_name], cwd=self.clone_dir)
        
        # Create GitHub PR
        pr_title = f"SCIM Group Sync: {username} membership changes"
        pr_body = self._generate_group_pr_body(username, modified_files)
        
        pr_url = self._create_github_pr(
            branch_name=branch_name,
            title=pr_title,
            body=pr_body,
            labels=['scim-provisioning', 'needs-review']
        )
        
        return pr_url

    def _run_git_command(self, command: List[str], cwd: Optional[Path] = None) -> str:
        """
        Run a git command with error handling.
        
        Args:
            command: List of command and arguments
            cwd: Working directory for the command
            
        Returns:
            Command output
            
        Raises:
            subprocess.CalledProcessError: If command fails
        """
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True,
                encoding='utf-8'
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"Git command failed: {' '.join(command)}")
            print(f"Error: {e.stderr}")
            raise

    def _create_github_pr(
        self, 
        branch_name: str, 
        title: str, 
        body: str, 
        labels: List[str]
    ) -> str:
        """
        Create a GitHub pull request using the GitHub API.
        
        Args:
            branch_name: Source branch name
            title: PR title
            body: PR body/description
            labels: List of label names to apply
            
        Returns:
            GitHub PR URL
            
        Raises:
            requests.RequestException: If API request fails
        """
        api_url = f"https://api.github.com/repos/{self.owner}/{self.repo_name}/pulls"
        
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json'
        }
        
        data = {
            'title': title,
            'body': body,
            'head': branch_name,
            'base': 'main'
        }
        
        # Create PR
        response = requests.post(api_url, headers=headers, json=data)
        response.raise_for_status()
        
        pr_data = response.json()
        pr_number = pr_data['number']
        pr_url = pr_data['html_url']
        
        # Add labels if provided
        if labels:
            labels_url = f"https://api.github.com/repos/{self.owner}/{self.repo_name}/issues/{pr_number}/labels"
            labels_data = {'labels': labels}
            
            labels_response = requests.post(labels_url, headers=headers, json=labels_data)
            # Don't fail if labels can't be added (they might not exist in the repo)
            if labels_response.status_code != 200:
                print(f"Warning: Could not add labels {labels} to PR #{pr_number}")
        
        return pr_url

    def _generate_user_pr_body(self, username: str, yaml_filename: str, yaml_content: str) -> str:
        """
        Generate PR body for user identity changes.
        
        Args:
            username: Username
            yaml_filename: YAML file name
            yaml_content: YAML file content
            
        Returns:
            Formatted PR body
        """
        # Extract key information from YAML content for summary
        lines = yaml_content.split('\n')
        email = None
        role = None
        team = None
        
        for line in lines:
            if 'email:' in line:
                email = line.split('email:')[-1].strip().strip('"\'')
            elif 'role:' in line and 'identity:' in yaml_content.split(line)[0]:
                role = line.split('role:')[-1].strip().strip('"\'')
            elif 'team:' in line:
                team = line.split('team:')[-1].strip().strip('"\'')
        
        body = f"""## SCIM User Provisioning

**User:** {username}
**Email:** {email or 'N/A'}
**Role:** {role or 'N/A'}
**Team:** {team or 'N/A'}
**File:** `{yaml_filename}`

### Summary
This PR adds or updates the identity configuration for {username} as part of SCIM provisioning from EntraID.

### Changes
- {'✅' if 'Add' in yaml_content else '🔄'} User identity YAML file: `identities/{yaml_filename}`
- 🔐 Configured for OIDC authentication via EntraID
- 👥 Group memberships will be managed separately if applicable

### Verification Checklist
- [ ] Review user details for accuracy
- [ ] Confirm role and team assignments
- [ ] Verify authentication configuration
- [ ] Check policies are appropriate for the user's role

### Next Steps
After merging this PR, run `terraform plan` and `terraform apply` to provision the user identity in Vault.

---
*This PR was automatically generated by the SCIM Bridge service.*
"""
        return body

    def _generate_group_pr_body(self, username: str, modified_files: List[str]) -> str:
        """
        Generate PR body for group membership changes.
        
        Args:
            username: Username
            modified_files: List of modified file paths
            
        Returns:
            Formatted PR body
        """
        body = f"""## SCIM Group Membership Update

**User:** {username}
**Modified Groups:** {len(modified_files)}

### Summary
This PR updates group memberships for {username} as part of SCIM group synchronization from EntraID.

### Modified Files
"""
        for file_path in modified_files:
            body += f"- `{file_path}`\n"
        
        body += f"""
### Changes
- 🔄 Updated entraid_human_identities lists in group files
- 👥 Synchronized group memberships from EntraID SCIM

### Verification Checklist
- [ ] Review group membership changes
- [ ] Confirm user should have access to these groups
- [ ] Check for any missing or extra group assignments

### Next Steps
After merging this PR, run `terraform plan` and `terraform apply` to update group memberships in Vault.

---
*This PR was automatically generated by the SCIM Bridge service.*
"""
        return body