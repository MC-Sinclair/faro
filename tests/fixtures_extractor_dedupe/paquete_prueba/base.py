class Cosa:
    def metodo(self):
        """Doc de metodo, para el test de deduplicación por identidad."""


class Base:
    def metodo_base(self):
        """Doc original de Base, para el test de herencia."""


class Hija(Base):
    """No sobreescribe metodo_base: debe resolver con la doc de Base."""


class HijaConOverride(Base):
    def metodo_base(self):
        """Doc propia de HijaConOverride: debe ganarle a la de Base."""


class SinDocumentar:
    """La clase sí documenta; el método no. Existe igual."""

    def metodo_sin_doc(self, cuantos: int = 3) -> str:
        return "x" * cuantos


from otro_paquete import BaseAjena as BaseAjena


class HeredaDeAjena(BaseAjena):
    """Hereda de una clase de otro_paquete: sus métodos heredados deben seguir
    marcándose como propios de paquete_prueba (spec 2026-07-19)."""
