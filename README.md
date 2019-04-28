# fauxcaml
> A (not so great) Python implementation of OCaml.

The `fauxcaml` compiler can convert simple OCaml code to 86x-64 ([NASM](https://en.wikipedia.org/wiki/Netwide_Assembler) flavored) assembly. Fauxcaml uses the type checking algorithm described in Luca Cardelli's 1988 paper [Basic Polymorphic Typechecking](http://lucacardelli.name/Papers/BasicTypechecking.pdf) and explained in [Bodil Stokke's excellent talk from 2018](https://www.youtube.com/watch?v=8coUL8G1lFA).

## Installing

The codebase uses recent features of Python quite extensively ([dataclasses](https://docs.python.org/3/library/dataclasses.html), [f-strings](https://www.python.org/dev/peps/pep-0498/), [type annotations](https://docs.python.org/3/library/typing.html)), so your system must have at least Python 3.7 installed.

### Ensure Python 3.7 Installed
Python 3.7 must be installed at the following location: `/usr/local/bin/python3.7`. Test to make sure this is the case.

```shell
$ if [ -f /usr/local/bin/python3.7 ]; then echo good; else echo bad; fi
```

### Clone and Install

```shell
$ git clone https://github.com/eignnx/fauxcaml.git
$ cd fauxcaml
$ bash install.sh  # Installs the `fauxcamlc` cli tool.
```

## Compiling a Program

Assuming your OCaml program is in a file called `test.ml`:

```shell
$ fauxcamlc test.ml
```

To run the executable produced:

```shell
$ ./test
```

## Running the Unit Tests

```shell
$ pytest
```

## Compilation Example

The following OCaml program...

```ocaml
let f x = x + 1;;
exit (f 100);;
```

...gets compiled to...

```assembly
extern malloc
global main
section .data
section .text

; <FnDef>
    main:
    enter 16, 0
    ; <CreateClosure recursive="False">
        mov rdi, 8
        call malloc
        mov r8, rax
        mov QWORD [r8], f
        mov QWORD [rbp-8], r8
    ; </CreateClosure>
    ; <CallClosure>
        mov rax, QWORD [rbp-8]
        push rax
        push QWORD 100
        call [rax]
        mov QWORD [rbp-16], rax
    ; </CallClosure>
    ; <Exit>
        mov rax, 60 ; code for `exit`
        mov rdi, QWORD [rbp-16]
        syscall
    ; </Exit>
    leave
    ret 0
; </FnDef>

; <FnDef>
    f:
    enter 8, 0
    ; <AddSub operation="+">
        mov rax, QWORD [rbp+16]
        add rax, QWORD 1
        mov QWORD [rbp-8], rax
    ; </AddSub>
    ; <Return>
        mov rax, QWORD [rbp-8]
        leave
        ret 16
    ; </Return>
    leave
    ret 16
; </FnDef>
```

## Contributing

I am open to contributions but it might be wise to wait until things stabilize a bit more (as of April 1st, 2019). If you're interested in contributing, please open an issue titled something like "can i help?", and I'll see what I can do to bring you on board!

## Project Structure

The `./fauxcaml` directory defines a top-level package. It contains the following sub-packages:

* `fauxcaml.tests`: All unit tests go here. This project uses the [pytest](https://docs.pytest.org/en/latest/) unit test framework.
* `fauxcaml.parsing`: Defines the lexer and parser. These components are not built from scratch, but use [`rply`](https://github.com/alex/rply), so the code in there is fairly high-level.
* `fauxcaml.semantics`: Contains semantic analysis code, and defines the abstract syntax tree data structure (see `syntax.py`).
  * `syntax.py`: Defines the abstract syntax tree (AST) data structure. Includes functions for type checking, and code generation. **This is an important file.**
  * `check.py`: Defines the core type checking **context** object
  * `typ.py`: Defines objects which represent OCaml types
  * `env.py`: Defines a dictionary-like class called `Env` which can reference parent `Env`s. Used in type checking to associate identifiers with types.
  * `std_env.py`: Defines **type signatures** for built-in functions
  * `unifier_set.py`: A class used in type checking for keeping track of which type variables have already been unified (shown to be equivalent). Derived from `DisjointSet` defined in `disjoint_set.py`.
* `fauxcaml.lir`: Defines the *low-level intermediate representation*. This acts as an API for programmatically constructing assembly files.
* `fauxcaml.build`: Contains high-level functions for compiling, assembling, and linking. 
* `fauxcaml.utils`: Random utility functions go here.
