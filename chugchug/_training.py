"""TrainingChug — purpose-built for ML training loops.

Uses the protocol under the hood (Tracker + Handler).
"""

from __future__ import annotations

from typing import Any, Iterable, Iterator, TypeVar

from ._bar import Chug

T = TypeVar("T")


class TrainingChug:
    """Progress bar designed for ML training loops.

    Usage:
        tracker = TrainingChug(epochs=10, steps_per_epoch=1000)
        for epoch in tracker.epochs():
            for batch in tracker.steps(dataloader):
                loss = train(batch)
                tracker.log(loss=loss, lr=optimizer.lr)
    """

    def __init__(
        self,
        epochs: int,
        steps_per_epoch: int | None = None,
        gradient: str = "fire",
        **kwargs: Any,
    ) -> None:
        self._epochs = epochs
        self._steps_per_epoch = steps_per_epoch
        self._gradient = gradient
        self._kwargs = kwargs
        self._epoch_bar: Chug | None = None
        self._step_bar: Chug | None = None
        self._current_epoch = 0

    def epochs(self) -> Iterator[int]:
        self._epoch_bar = Chug(
            total=self._epochs,
            desc="Epochs",
            gradient=self._gradient,
            unit="epoch",
            **self._kwargs,
        )
        for e in range(self._epochs):
            self._current_epoch = e
            yield e
            self._epoch_bar.update()
        self._epoch_bar.close()

    def steps(self, iterable: Iterable[T]) -> Iterator[T]:
        total = self._steps_per_epoch
        if total is None:
            try:
                total = len(iterable)  # type: ignore
            except TypeError:
                total = None

        self._step_bar = Chug(
            iterable,
            desc=f"Epoch {self._current_epoch + 1}/{self._epochs}",
            total=total,
            gradient="ocean",
            leave=False,
        )
        return iter(self._step_bar)

    def log(self, **metrics: Any) -> None:
        formatted = {
            k: f"{v:.4f}" if isinstance(v, float) else str(v)
            for k, v in metrics.items()
        }
        if self._step_bar:
            self._step_bar.set_metrics(**formatted)
        if self._epoch_bar:
            self._epoch_bar.set_metrics(**formatted)
