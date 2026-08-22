"""Handlers package.

Submodules are imported explicitly by ``bot.create_dispatcher``. Keeping this
package initializer side-effect free prevents retired/legacy routers from
being imported merely because the package is loaded.
"""
