"""
# High-level Intermediate Representation (HIR)

## Rules

    * Each instruction has type information associated with it.

    * All nested expressions (ie 1 + 2 * 4 / arr[i] + f 3) will be broken up
      and turned into a sequence of "3-address-flavored" instructions using
      `hir.Temp` values to store intermediate results.

    * All instructions will have a method called `to_lir` which converts
      it into the Low-level Intermediate Representation (see the `fauxcaml.lir`
      package).

    * All `syntax.Ident` values will be replaced with either `hir.Local` or
      `hir.Capture` values.

            * An `hir.Local` value represents a local variable in the current
              function's stack frame. All `hir.Temp` values will be
              given GLOBALLY UNIQUE IDs.

            * An `hir.Capture` value represents a non-local variable that was
              used in a nested function's body. Each `hir.Capture` is described
              by a list of indices

      EX:

        ```ocaml
        f x
        ```

        Translates to:

        ```python
        hir.Call(hir.Temp(1234), hir.Ident("f"), hir.Ident("x"))
        ```

        In this case, Temp(1234) is the place that the result of `f x` is
        stored.
"""