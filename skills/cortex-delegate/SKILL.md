---
name: cortex-delegate
description: Create explicitly requested separate Codex worktree tasks or ChatGPT Work cloud tasks, then keep review and final judgment in an Astra-led parent. Use when the user asks for a new or separate task in Codex or Work. Do not create visible tasks for ordinary subagent delegation.
---

# Cortex delegate

Use the strongest model in the parent task for decomposition, review, and synthesis. Send bounded execution to the cheapest lane that has the required context.

This skill creates visible, user-owned tasks. It is not an invisible subagent mechanism. Only create one when the user explicitly asks for a **new or separate task**. Phrases such as *create a new task*, *spin this into a separate task*, or *start a Work task* qualify. *Delegate this* or *use a subagent* alone does not qualify unless the surrounding request clearly identifies a separate Codex or Work task. Use the runtime's subagent tools for ordinary bounded subtasks. If the user's intended surface is genuinely ambiguous and changes the outcome, ask one concise question before creating anything.

## Choose the lane

| Work needs | Lane |
|---|---|
| Local repository, terminal, tests, or a diff | Codex project task |
| Isolated implementation in a Git repository | Codex worktree task |
| Research, documents, connected apps, or a cloud deliverable without local repository state | ChatGPT Work |
| Local files that are not already available to ChatGPT Work | Codex local task, or ask the user to attach the files to Work |

Do not send coding work to ChatGPT Work merely because it is cloud-hosted. Do not send connected-app research to a local worktree merely because the parent is in Codex.

## Parent contract

The parent, normally Astra, keeps the judgment:

1. Decompose the request into independent tasks with explicit acceptance criteria.
2. Dispatch only tasks that can succeed with the context available in their lane.
3. Inspect the returned output and evidence. Do not forward a child task's conclusion unreviewed.
4. Send concrete revision requests back to the same task when needed.
5. Integrate the results and make the final call in the parent.

Keep delegation bounded. Default to one task. Use parallel tasks only when the work is genuinely independent, and keep the number small enough that the parent can review every result.

## Codex project tasks

Use the Codex app task tools, not a shell wrapper.

1. Call `list_projects` and resolve the exact saved project. Never invent a project ID.
2. For a Git repository, create a worktree task by default. Use the saved project directly only when the user explicitly asks for it or when the task must operate on the current checkout.
   For a saved non-Git project, use its local environment because a worktree is unavailable.
3. Start from the project's default branch unless the user explicitly names another starting state. Use `working-tree` only when the child must see current uncommitted changes.
4. Choose the worker model by task shape, using only models exposed in the current session. The current preferred map is:
   - `gpt-5.6-luna`, low or medium, for mechanical and tightly specified work.
   - `gpt-5.6-terra`, medium or high, for ordinary implementation.
   - `gpt-5.6-sol`, high or xhigh, for complex implementation or debugging.
   - Astra only for a second hard problem that independently needs frontier judgment. Do not clone the parent by default.

   If a preferred model is unavailable, choose the closest exposed model by capability and cost. Never invent a model slug from this document.
5. The prompt must name the deliverable, repository scope, relevant files or starting evidence, constraints, acceptance criteria, and verification commands. State that the child must not merge or push unless the user requested it.
6. After creation, use `wait_threads` with the returned task ID and host ID. Poll once, then use bounded waits with the returned cursor rather than repeatedly reading unchanged state.
7. Read the result and inspect the diff or evidence. If revision is required, use `send_message_to_thread` with file-and-line findings or a failing check.

Creating a Codex task is non-blocking. A returned `clientThreadId` means worktree setup is still in progress and must not be passed to tools that require a ready `threadId`.

## ChatGPT Work tasks

Use Work for cloud knowledge work, not as a cheaper coding model.

1. Call `list_projects`. Use a returned ChatGPT project ID only when its files and instructions are relevant. Otherwise create a projectless Work task.
2. Create the task with target type `chatgptWorkCloud`. Omit model and reasoning settings because Work chooses those in its own environment.
3. Put all required context in the prompt. Local files, credentials, saved memories, and local project instructions are not transferred automatically. If a required local file cannot be attached through the available task interface, do not dispatch blindly.
4. Treat the Work task as a separate cloud conversation. It syncs across ChatGPT web, mobile, and desktop, but it does not automatically return a reviewed result into the parent Codex task.
5. Use `read_thread` to inspect it when appropriate and `send_message_to_thread` for revisions. Do not use `wait_threads` for a Work task. It is reserved for Codex tasks.

Connected-app permissions and approval requirements still apply inside Work. Delegation does not broaden the user's authority or transfer local secrets.

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
