import ast
import asyncio
import collections


def patch(cls: type) -> collections.abc.Callable:
    def wrap(func: collections.abc.Callable) -> collections.abc.Callable:
        if hasattr(func, "_patch"):
            func._patch.append(cls)
        else:
            func._patch = [cls]

        return func

    return wrap


async def aexec(command: str, kwargs: dict = {}) -> object:
    temp = {}
    name = "aexec"

    body = ast.parse(command, "exec").body
    if body and isinstance(body[-1], ast.Expr):
        body[-1] = ast.Return(value=body[-1].value)

    node = ast.Module(
        body=[
            ast.AsyncFunctionDef(
                name=name,
                args=ast.arguments(
                    posonlyargs=[],
                    args=[ast.arg(arg=key) for key in kwargs],
                    kwonlyargs=[],
                    kw_defaults=[],
                    defaults=[],
                ),
                body=body,
                decorator_list=[],
            )
        ],
        type_ignores=[],
    )
    ast.fix_missing_locations(node)

    exec(compile(node, "<string>", "exec"), temp)

    return await temp[name](**kwargs)


async def shell(command: str) -> str:
    subprocess = await asyncio.create_subprocess_shell(
        command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await subprocess.communicate()
        return (stdout + stderr).decode("utf-8").rstrip()
    except asyncio.CancelledError:
        subprocess.kill()
        await subprocess.wait()
        raise


def usecs(s: float) -> str:
    if not s:
        return "0 s"

    if s >= 1:
        return f"{s:.2f} s"

    if s >= 0.001:
        return f"{s * 1000:.2f} ms"

    return f"{s * 1000000:.2f} µs"
