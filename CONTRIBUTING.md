# Contributing to Seasonalbot

Seasonalbot is a community project for the Python Discord community over at https://discord.gg/python. We will be providing support for those of you who are new to Git, and this project is to be considered educational.

Our projects are open-source and are automatically deployed whenever commits are pushed to the `master` branch on each repository, so we've created a set of guidelines in order to keep everything clean and in working order.

Note that contributions may be rejected on the basis of a contributor failing to follow these guidelines.

## Rules

1. You must be a member of [our Discord community](https://discord.gg/python) in order to contribute to this project.
2. Your pull request must solve an issue created or approved by a staff member. These will be labeled with the `approved` label. Feel free to suggest issues of your own, which staff can review for approval.
3. **No force-pushes** or modifying the Git history in any way.
4. If you have direct access to the repository, **create a branch for your changes** and create a pull request for that branch. If not, create a branch on a fork of the repository and create a pull request from there.
    * It's common practice for a repository to reject direct pushes to `master`, so make branching a habit!
    * If PRing from your own fork, **ensure that "Allow edits from maintainers" is checked**. This gives permission for maintainers to commit changes directly to your fork, speeding up the review process.
5. **Adhere to the prevailing code style**, which we enforce using [flake8](http://flake8.pycqa.org/en/latest/index.html).
    * Run `flake8` against your code **before** you push it. Your commit will be rejected by the build server if it fails to lint.
    * [Git Hooks](https://git-scm.com/book/en/v2/Customizing-Git-Git-Hooks) are a powerful tool that can be a daunting to set up. Fortunately, [`pre-commit`](https://github.com/pre-commit/pre-commit) abstracts this process away from you and is provided as a dev dependency for this project. Run `pipenv run precommit` when setting up the project and you'll never have to worry about breaking the build for linting errors.
6. **Make great commits**. A well structured git log is key to a project's maintainability; it efficiently provides insight into when and *why* things were done for future maintainers of the project.
    * Commits should be as narrow in scope as possible. Commits that span hundreds of lines across multiple unrelated functions and/or files are very hard for maintainers to follow. After about a week they'll probably be hard for you to follow too.
    * Try to avoid making minor commits for fixing typos or linting errors. Since you've already set up a pre-commit hook to run `flake8` before a commit, you shouldn't be committing linting issues anyway.
    * A more in-depth guide to writing great commit messages can be found in Chris Beam's [*How to Write a Git Commit Message*](https://chris.beams.io/posts/git-commit/)
7. **Avoid frequent pushes to the main repository**. This goes for PRs opened against your fork as well. Our test build pipelines are triggered every time a push to the repository (or PR) is made. Try to batch your commits until you've finished working for that session, or you've reached a point where collaborators need your commits to continue their own work. This also provides you the opportunity to amend commits for minor changes rather than having to commit them on their own because you've already pushed.
    * This includes merging master into your branch. Try to leave merging from master for after your PR passes review; a maintainer will bring your PR up to date before merging. Exceptions to this include: resolving merge conflicts, needing something that was pushed to master for your branch, or something was pushed to master that could potentionally affect the functionality of what you're writing.
8. **Don't fight the framework**. Every framework has its flaws, but the frameworks we've picked out have been carefully chosen for their particular merits. If you can avoid it, please resist reimplementing swathes of framework logic - the work has already been done for you!
9. If someone is working on an issue or pull request, **do not open your own pull request for the same task**. Instead, collaborate with the author(s) of the existing pull request. Duplicate PRs opened without communicating with the other author(s) and/or PyDis staff will be closed. Communication is key, and there's no point in two separate implementations of the same thing.
    * One option is to fork the other contributor's repository and submit your changes to their branch with your own pull request. We suggest following these guidelines when interacting with their repository as well.
    * The author(s) of inactive PRs and claimed issues will be be pinged after a week of inactivity for an update. Continued inactivity may result in the issue being released back to the community and/or PR closure.
10. **Work as a team** and collaborate wherever possible. Keep things friendly and help each other out - these are shared projects and nobody likes to have their feet trodden on.
11. **Internal projects are internal**. As a contributor, you have access to information that the rest of the server does not. With this trust comes responsibility - do not release any information you have learned as a result of your contributor position. We are very strict about announcing things at specific times, and many staff members will not appreciate a disruption of the announcement schedule.
12. All static content, such as images or audio, **must be licensed for open public use**.
    * Static content must be hosted by a service designed to do so. Failing to do so is known as "leeching" and is frowned upon, as it generates extra bandwidth costs to the host without providing benefit. It would be best if appropriately licensed content is added to the repository itself so it can be served by PyDis' infrastructure.

Above all, the needs of our community should come before the wants of an individual. Work together, build solutions to problems and try to do so in a way that people can learn from easily. Abuse of our trust may result in the loss of your Contributor role, especially in relation to Rule 7.

## Changes to this arrangement

All projects evolve over time, and this contribution guide is no different. This document is open to pull requests or changes by contributors. If you believe you have something valuable to add or change, please don't hesitate to do so in a PR.

##  Supplemental Information
### Developer Environment
Seasonalbot utilizes [Pipenv](https://pipenv.readthedocs.io/en/latest/) for installation and dependency management. For users unfamiliar with the Pipenv workflow, Pipenv's documentation provides a [Basic Usage](https://pipenv.readthedocs.io/en/latest/basics/) tutorial, along with some of the more advanced workflows. A project-specific installation guide can be found in [Seasonalbot's README](https://github.com/python-discord/seasonalbot/blob/master/README.md).

When pulling down changes from GitHub, remember to sync your environment using `pipenv sync --dev` to ensure you're using the most up-to-date versions the project's dependencies.

### Type Hinting
[PEP 484](https://www.python.org/dev/peps/pep-0484/) formally specifies type hints for Python functions, added to the Python Standard Library in version 3.5. Type hints are recognized by most modern code editing tools and provide useful insight into both the input and output types of a function, preventing the user from having to go through the codebase to determine these types.

For example:

```py
def foo(input_1: int, input_2: dict) -> bool:
```

Tells us that `foo` accepts an `int` and a `dict` and returns a `bool`.

All function declarations should be type hinted in code contributed to the PyDis organization.

For more information, see *[PEP 483](https://www.python.org/dev/peps/pep-0483/) - The Theory of Type Hints* and Python's documentation for the [`typing`](https://docs.python.org/3/library/typing.html) module.

### AutoDoc Formatting Directives
Many documentation packages provide support for automatic documentation generation from the codebase's docstrings. These tools utilize special formatting directives to enable richer formatting in the generated documentation.

For example:

```py
def foo(bar: int, baz: dict=None) -> bool:
    """
    Does some things with some stuff.

    :param bar: Some input
    :param baz: Optional, some other input

    :return: Some boolean
    """
```

Since PyDis does not utilize automatic documentation generation, use of this syntax should not be used in code contributed to the organization. Should the purpose and type of the input variables not be easily discernable from the variable name and type annotation, a prose explanation can be used. Explicit references to variables, functions, classes, etc. should be wrapped with backticks (`` ` ``).

For example, the above docstring would become:

```py
def foo(bar: int, baz: dict=None) -> bool:
    """
    Does some things with some stuff.

    This function takes an index, `bar` and checks for its presence in the database `baz`, passed as a dictionary.

    Returns `False` if `baz` is not passed.
    """
```

### Logging levels
The project currently defines [`logging`](https://docs.python.org/3/library/logging.html) levels as follows:
* **TRACE:** Use this for tracing every step of a complex process. That way we can see which step of the process failed. Err on the side of verbose. **Note:** This is a PyDis-implemented logging level.
* **DEBUG:** Someone is interacting with the application, and the application is behaving as expected.
* **INFO:** Something completely ordinary happened. Like a cog loading during startup.
* **WARNING:** Someone is interacting with the application in an unexpected way or the application is responding in an unexpected way, but without causing an error.
* **ERROR:** An error that affects the specific part that is being interacted with
* **CRITICAL:** An error that affects the whole application.

### Work in Progress (WIP) PRs
Github [has introduced a new PR feature](https://github.blog/2019-02-14-introducing-draft-pull-requests/) that allows the PR author to mark it as a WIP. This provides both a visual and functional indicator that the contents of the PR are in a draft state and not yet ready for formal review.

This feature should be utilized in place of the traditional method of prepending `[WIP]` to the PR title.

As stated earlier, **ensure that "Allow edits from maintainers" is checked**. This gives permission for maintainers to commit changes directly to your fork, speeding up the review process.

## Footnotes

This document was inspired by the [Glowstone contribution guidelines](https://github.com/GlowstoneMC/Glowstone/blob/dev/docs/CONTRIBUTING.md).
