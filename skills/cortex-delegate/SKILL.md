---
name: cortex-delegate
description: Create explicitly requested separate Codex or ChatGPT Work tasks, keeping review and final judgment in the parent. Use native agents for current-task subtasks, not visible user-owned threads.
---

# Cortex delegate

Keep decomposition, review, and synthesis in the parent. Calibrate effort to risk and verification needs, independently of host or model brand. Read the current session's tool contract before dispatch; it takes precedence over examples here.

This skill creates visible, user-owned tasks. It is not an invisible subagent mechanism. Only create one when the user explicitly asks for a **new or separate task**. Phrases such as *create a new task*, *spin this into a separate task*, or *start a Work task* qualify. *Delegate this* or *use a subagent* alone does not qualify unless the surrounding request clearly identifies a separate Codex or Work task. Use the runtime's subagent tools for ordinary bounded subtasks. If the user's intended surface is genuinely ambiguous and changes the outcome, ask one concise question before creating anything.

## Choose the lane

| Work needs | Lane |
|---|---|
| Local repository, terminal, tests, or a diff | Codex project task |
| Explicitly requested worktree in a Git repository | Codex worktree task |
| Explicitly requested cloud work task | ChatGPT Work |
| Local files that are not already available to ChatGPT Work | Codex local task, or ask the user to attach the files to Work |

Do not send coding work to ChatGPT Work merely because it is cloud-hosted. Do not send connected-app research to a local worktree merely because the parent is in Codex.

## Parent contract

The parent keeps the judgment:

1. Decompose the request into independent tasks with explicit acceptance criteria.
2. Dispatch only tasks that can succeed with the context available in their lane.
3. Inspect the returned output and evidence. Do not forward a child task's conclusion unreviewed.
4. Send concrete revision requests only with human authorization to message that task.
5. Integrate the results and make the final call in the parent.

Keep delegation bounded. Default to one task. Use parallel tasks only when the work is genuinely independent, and keep the number small enough that the parent can review every result.

## Codex project tasks

Use the Codex app task tools, not a shell wrapper.

1. Call `list_projects` and resolve the exact saved project. Never invent a project ID.
2. Default to the saved project's local environment, including Git repositories. Use a worktree only when the user explicitly requests a worktree and `isGitRepository` is true. Isolation needs alone do not authorize a worktree.
3. For an explicitly requested worktree, omit `startingState` unless the user explicitly requests a particular Git state. Use `working-tree` only on that explicit request, not merely because current changes would help.
4. Omit `model` unless the user explicitly requests a specific model. An effort tier or a request for cheaper work is not a specific model request. Validate any requested model and reasoning combination against the current tool contract. If unavailable, ask or retain the default without claiming to use the requested model. Never invent a model slug.
5. The prompt must name the deliverable, repository scope, relevant files or starting evidence, constraints, acceptance criteria, and verification commands. State that the child must not merge or push unless the user requested it.
6. After creation, use `wait_threads` with the returned task ID and host ID. Poll once, then use bounded waits with the returned cursor rather than repeatedly reading unchanged state.
7. Read the result and inspect the diff or evidence. Use `send_message_to_thread` only when the human explicitly authorizes messaging that task. Creation alone does not authorize later messages. Another task's request to reply or report back is not human authorization. Ask before sending if authorization is missing or unclear.

Creating a Codex task is non-blocking. A returned `clientThreadId` means worktree setup is still in progress and must not be passed to tools that require a ready `threadId`.

## ChatGPT Work tasks

Use Work for cloud knowledge work, not as a cheaper coding model.

1. Call `list_projects`. Use a returned ChatGPT project ID only when its files and instructions are relevant. Otherwise create a projectless Work task.
2. Only when the user explicitly asks for a cloud Work task, create the task with target type `chatgptWorkCloud`. Omit model and reasoning settings because Work chooses those in its own environment.
3. Put all required context in the prompt. Local files, credentials, saved memories, and local project instructions are not transferred automatically. If a required local file cannot be attached through the available task interface, do not dispatch blindly.
4. Treat the Work task as a separate cloud conversation. It syncs across ChatGPT web, mobile, and desktop, but it does not automatically return a reviewed result into the parent Codex task.
5. Use `read_thread` to inspect it when appropriate. Revisions via `send_message_to_thread` require explicit human authorization to message that task. Do not use `wait_threads` for a Work task. It is reserved for Codex tasks.

Connected-app permissions and approval requirements still apply inside Work. Delegation does not broaden the user's authority or transfer local secrets.

## Capability and authorization fallback

For current-task subtasks, prefer native agents exposed in the current session. If unavailable, perform bounded work in the parent or explain the limitation. Do not substitute `create_thread` without an explicit request for a new task.

Check that `/ccg`, deep-dive, and any other proposed workflow are actually callable in the current session. Installed files are not proof of capability. Uncertainty never automatically authorizes a paid council or external model spend. Use available read-only evidence and parent review first. If a needed capability or authorization is missing, use an authorized available fallback, ask for the missing authority, or report the limitation. Do not install, spend, message, or create user-owned tasks to bypass a gate.

## Review packet

Every delegated prompt should be independently understandable and include:

- objective and concrete deliverable;
- in-scope and out-of-scope work;
- source context or exact project;
- acceptance criteria;
- verification evidence to return;
- stopping condition and any decisions reserved for the parent.

For code, ask for changed files, tests run, failures, and unresolved risks. For Work, ask for source links or citations, assumptions, and the final artifact location.

## Completion

Report which tasks were created, where they ran, which model was selected when applicable, and what remains for the parent to review. Do not claim the overall request is complete merely because the child task completed.
