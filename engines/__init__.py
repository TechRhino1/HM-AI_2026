"""
LEGACY ENGINES PACKAGE — DEPRECATED.

Notice: All active execution paths, risk management, market intelligence,
analyst models, state management, and backtesting pipelines have been consolidated
into the modern 'jarvis/' package.

The 'engines/' module is retained strictly for backward compatibility and
historical test suites. Do not introduce new features here; please use 'jarvis/'.
"""
import warnings

warnings.warn(
    "The 'engines' package is deprecated. All core execution and intelligence logic "
    "has been consolidated into the 'jarvis' package.",
    DeprecationWarning,
    stacklevel=2
)
