from __future__ import annotations

import threading
import typing as t
import uuid

from channels.generic.websocket import WebsocketConsumer
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User as DjangoUser

from ring import Ring

from magiccube.collections.cube import Cube

from draft.draft import Draft, Drafter

User: DjangoUser = get_user_model()


class DraftSlot(object):

    def __init__(self, draft: Draft, drafter: Drafter):
        self._draft: Draft = draft
        self._drafter = drafter
        self._consumer: t.Optional[WebsocketConsumer] = None

    @property
    def draft(self) -> Draft:
        return self._draft

    @property
    def drafter(self) -> Drafter:
        return self._drafter

    @property
    def consumer(self) -> t.Optional[WebsocketConsumer]:
        return self._consumer

    def __hash__(self) -> int:
        return hash((self._draft, self._drafter))

    def __eq__(self, other):
        return (
            isinstance(other, self.__class__)
            and self._draft == other._draft
            and self._drafter == other._drafter
        )


class DraftCoordinator(object):

    def __init__(self):
        # self._drafts: t.MutableMapping[Draft, t.FrozenSet[Drafter]] = {}
        # self._drafts: t.MutableMapping[uuid.UUID, Draft] = {}
        self._drafts: t.MutableSet[Draft] = set()
        self._drafters: t.MutableMapping[uuid.UUID, DraftSlot] = {}

        self._lock = threading.Lock()

    # def get_draft(self, key: uuid.UUID) -> t.Optional[Draft]:
    #     with self._lock:
    #         return self._drafts.get(key)

    def get_draft_slot(self, key: uuid.UUID) -> t.Optional[DraftSlot]:
        with self._lock:
            return self._drafters.get(key)

    def start_draft(self, users: t.Iterable[User], cube: Cube) -> None:
        drafters = Ring(
            Drafter(
                user.username,
                uuid.uuid4(),
            )
            for user in
            users
        )
        draft = Draft(
            uuid.uuid4(),
            drafters,
            cube,
        )

        with self._lock:
            self._drafts.add(draft)

            for drafter in drafters.all:
                self._drafters[drafter.key] = DraftSlot(
                    draft,
                    drafter,
                )

        draft.start()

    def connect_drafter(self, draft_slot: DraftSlot, consumer: WebsocketConsumer) -> None:
        with self._lock:
            draft_slot._consumer = consumer

    def disconnect_drafter(self, draft_slot: DraftSlot) -> None:
        with self._lock:
            draft_slot._consumer = None

    def draft_complete(self, draft) -> None:
        with self._lock:
            for drafter in draft.drafters:
                del self._drafters[drafter.key]
            self._drafts.discard(draft)


DRAFT_COORDINATOR = DraftCoordinator()