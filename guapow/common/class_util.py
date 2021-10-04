from abc import ABC
from typing import Type, List, Optional, TypeVar

ANY_CLASS = TypeVar("ANY_CLASS")


def instantiate_subclasses(root: Type[ANY_CLASS]) -> Optional[List[ANY_CLASS]]:
    instances = []

    root_subs = root.__subclasses__()

    if root_subs:
        for sub in root_subs:
            if ABC not in sub.__bases__:
                instances.append(sub())

            children = instantiate_subclasses(sub)

            if children:
                instances.extend(children)

    return instances if instances else None
