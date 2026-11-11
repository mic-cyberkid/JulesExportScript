"""Google Jules API Models and Data Structures.

Represents REST API resources defined by the Google Jules API v1alpha.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class GitHubRepo:
    owner: str = ""
    repo: str = ""
    is_private: bool = False
    default_branch: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GitHubRepo:
        default_branch = ""
        db_obj = data.get("defaultBranch")
        if isinstance(db_obj, dict):
            default_branch = db_obj.get("displayName", "")
        elif isinstance(db_obj, str):
            default_branch = db_obj
        return cls(
            owner=data.get("owner", ""),
            repo=data.get("repo", ""),
            is_private=data.get("isPrivate", False),
            default_branch=default_branch,
            raw_data=data,
        )


@dataclass
class Source:
    name: str = ""
    id: str = ""
    github_repo: Optional[GitHubRepo] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Source:
        gh = None
        if "githubRepo" in data and isinstance(data["githubRepo"], dict):
            gh = GitHubRepo.from_dict(data["githubRepo"])
        return cls(
            name=data.get("name", ""),
            id=data.get("id", ""),
            github_repo=gh,
            raw_data=data,
        )


@dataclass
class PullRequest:
    url: str = ""
    title: str = ""
    description: str = ""
    base_ref: Optional[str] = None
    head_ref: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PullRequest:
        return cls(
            url=data.get("url", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            base_ref=data.get("baseRef"),
            head_ref=data.get("headRef"),
            raw_data=data,
        )


@dataclass
class GitPatch:
    unidiff_patch: str = ""
    base_commit_id: str = ""
    suggested_commit_message: str = ""
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GitPatch:
        return cls(
            unidiff_patch=data.get("unidiffPatch", ""),
            base_commit_id=data.get("baseCommitId", ""),
            suggested_commit_message=data.get("suggestedCommitMessage", ""),
            raw_data=data,
        )


@dataclass
class ChangeSet:
    source: str = ""
    git_patch: Optional[GitPatch] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ChangeSet:
        gp = None
        if "gitPatch" in data and isinstance(data["gitPatch"], dict):
            gp = GitPatch.from_dict(data["gitPatch"])
        return cls(
            source=data.get("source", ""),
            git_patch=gp,
            raw_data=data,
        )


@dataclass
class Media:
    data: str = ""  # Base64 encoded
    mime_type: str = ""
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Media:
        return cls(
            data=data.get("data", ""),
            mime_type=data.get("mimeType", ""),
            raw_data=data,
        )


@dataclass
class BashOutput:
    command: str = ""
    output: str = ""
    exit_code: Optional[int] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BashOutput:
        return cls(
            command=data.get("command", ""),
            output=data.get("output", ""),
            exit_code=data.get("exitCode"),
            raw_data=data,
        )


@dataclass
class Artifact:
    change_set: Optional[ChangeSet] = None
    media: Optional[Media] = None
    bash_output: Optional[BashOutput] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def kind(self) -> str:
        if self.change_set is not None:
            return "changeSet"
        if self.media is not None:
            return "media"
        if self.bash_output is not None:
            return "bashOutput"
        return "unknown"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Artifact:
        cs = ChangeSet.from_dict(data["changeSet"]) if "changeSet" in data else None
        med = Media.from_dict(data["media"]) if "media" in data else None
        bo = BashOutput.from_dict(data["bashOutput"]) if "bashOutput" in data else None
        return cls(
            change_set=cs,
            media=med,
            bash_output=bo,
            raw_data=data,
        )


@dataclass
class PlanStep:
    id: str = ""
    title: str = ""
    description: str = ""
    index: int = 0
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PlanStep:
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            index=data.get("index", 0),
            raw_data=data,
        )


@dataclass
class Plan:
    id: str = ""
    steps: List[PlanStep] = field(default_factory=list)
    create_time: str = ""
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Plan:
        steps = [PlanStep.from_dict(s) for s in data.get("steps", []) if isinstance(s, dict)]
        return cls(
            id=data.get("id", ""),
            steps=steps,
            create_time=data.get("createTime", ""),
            raw_data=data,
        )


@dataclass
class Activity:
    id: str = ""
    name: str = ""
    create_time: str = ""
    originator: str = ""
    description: str = ""
    artifacts: List[Artifact] = field(default_factory=list)
    agent_message: Optional[str] = None
    user_message: Optional[str] = None
    plan: Optional[Plan] = None
    plan_id_approved: Optional[str] = None
    progress_title: Optional[str] = None
    progress_description: Optional[str] = None
    is_session_completed: bool = False
    session_failed_reason: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def activity_type(self) -> str:
        if self.agent_message is not None:
            return "agentMessaged"
        if self.user_message is not None:
            return "userMessaged"
        if self.plan is not None:
            return "planGenerated"
        if self.plan_id_approved is not None:
            return "planApproved"
        if self.progress_title is not None or self.progress_description is not None:
            return "progressUpdated"
        if self.is_session_completed:
            return "sessionCompleted"
        if self.session_failed_reason is not None:
            return "sessionFailed"
        return "generic"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Activity:
        artifacts = [Artifact.from_dict(a) for a in data.get("artifacts", []) if isinstance(a, dict)]
        agent_msg = data.get("agentMessaged", {}).get("agentMessage") if "agentMessaged" in data else None
        user_msg = data.get("userMessaged", {}).get("userMessage") if "userMessaged" in data else None
        plan = None
        if "planGenerated" in data and isinstance(data["planGenerated"], dict):
            p_data = data["planGenerated"].get("plan")
            if isinstance(p_data, dict):
                plan = Plan.from_dict(p_data)
        plan_appr = data.get("planApproved", {}).get("planId") if "planApproved" in data else None
        prog_title = None
        prog_desc = None
        if "progressUpdated" in data and isinstance(data["progressUpdated"], dict):
            prog_title = data["progressUpdated"].get("title")
            prog_desc = data["progressUpdated"].get("description")
        is_completed = "sessionCompleted" in data
        failed_reason = data.get("sessionFailed", {}).get("reason") if "sessionFailed" in data else None

        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            create_time=data.get("createTime", ""),
            originator=data.get("originator", ""),
            description=data.get("description", ""),
            artifacts=artifacts,
            agent_message=agent_msg,
            user_message=user_msg,
            plan=plan,
            plan_id_approved=plan_appr,
            progress_title=prog_title,
            progress_description=prog_desc,
            is_session_completed=is_completed,
            session_failed_reason=failed_reason,
            raw_data=data,
        )


@dataclass
class Session:
    id: str = ""
    name: str = ""
    title: str = ""
    prompt: str = ""
    source: str = ""
    starting_branch: str = ""
    automation_mode: str = ""
    require_plan_approval: bool = False
    state: str = ""
    url: str = ""
    create_time: str = ""
    update_time: str = ""
    pull_requests: List[PullRequest] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Session:
        sc = data.get("sourceContext", {})
        source_name = sc.get("source", "") if isinstance(sc, dict) else ""
        starting_branch = ""
        if isinstance(sc, dict):
            ghc = sc.get("githubRepoContext", {})
            if isinstance(ghc, dict):
                starting_branch = ghc.get("startingBranch", "")

        prs = []
        for out in data.get("outputs", []):
            if isinstance(out, dict) and "pullRequest" in out and isinstance(out["pullRequest"], dict):
                prs.append(PullRequest.from_dict(out["pullRequest"]))

        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            title=data.get("title", ""),
            prompt=data.get("prompt", ""),
            source=source_name,
            starting_branch=starting_branch,
            automation_mode=data.get("automationMode", ""),
            require_plan_approval=data.get("requirePlanApproval", False),
            state=data.get("state", ""),
            url=data.get("url", ""),
            create_time=data.get("createTime", ""),
            update_time=data.get("updateTime", ""),
            pull_requests=prs,
            raw_data=data,
        )
