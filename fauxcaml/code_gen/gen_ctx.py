import contextlib
import itertools

from fauxcaml.code_gen import ir
from fauxcaml.semantics import typ, env


class CodeGenContext:
    def __init__(self):
        self.temp_generator = itertools.count()
        self.label_generator = itertools.count()

        param = ir.Ident("$unit", typ.Unit)  # Inaccessible var for the unit arg.
        self.current_fn = ir.FnDecl(self.new_label(), param, [], env.Env())
        self.fns = [self.current_fn]

    def new_temp(self, type: typ.Type):
        i = next(self.temp_generator)
        return ir.Temp(i, type)

    def new_label(self):
        i = next(self.label_generator)
        return ir.Label(i)

    def emit(self, instruction: ir.Instr):
        self.current_fn.body.append(instruction)

    def new_fn_decl(self, param_name: str, type: typ.Type):
        label = self.new_label()
        param_type, _ = type  # Unpack type to get parameter type
        param = ir.Ident(param_name, param_type)
        new_env = env.Env(parent=self.current_fn.env)
        return ir.FnDecl(label, param, [], new_env)

    @contextlib.contextmanager
    def define_fn(self, param_name: str, type: typ.Type):
        old_fn = self.current_fn
        self.current_fn = self.new_fn_decl(param_name, type)
        self.fns.append(self.current_fn)
        yield self.current_fn.label
        self.current_fn = old_fn
