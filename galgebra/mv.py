"""
Multivector and Linear Multivector Differential Operator
"""

import copy
import numbers
import operator
from functools import reduce

from sympy import (
    Symbol, Function, S, expand, Add,
    sin, cos, sinh, cosh, sqrt, trigsimp, expand,
    simplify, diff, Rational, Expr, Abs, collect,
)
from sympy import exp as sympy_exp
from sympy import N as Nsympy

from . import printer
from . import metric
from .printer import ZERO_STR
from .utils import _KwargParser
from . import dop

ONE = S(1)
ZERO = S(0)
HALF = Rational(1, 2)

half = Rational(1, 2)

########################### Multivector Class ##########################


class Mv(object):
    """
    Wrapper class for multivector objects (``self.obj``) so that it is easy
    to overload operators (``*``, ``^``, ``|``, ``<``, ``>``)  for the various
    multivector products and for printing.

    Also provides a constructor to easily instantiate multivector objects.

    Additionally, the functionality
    of the multivector derivative have been added via the special vector
    ``grad`` so that one can take the geometric derivative of a multivector
    function ``A`` by applying ``grad`` from the left, ``grad*A``, or the
    right ``A*grad`` for both the left and right derivatives.  The operator
    between the ``grad`` and the 'A' can be any of the multivector product
    operators.

    If ``f`` is a scalar function ``grad*f`` is the usual gradient of a function.
    If ``A`` is a vector function ``grad|f`` is the divergence of ``A`` and
    ``-I*(grad^A)`` is the curl of ``A`` (I is the pseudo scalar for the geometric
    algebra)

    Attributes
    ----------
    obj : sympy.core.Expr
        The underlying sympy expression for this multivector
    """

    ################### Multivector initialization #####################

    fmt = 1
    latex_flg = False
    restore = False
    dual_mode_lst = ['+I','I+','+Iinv','Iinv+','-I','I-','-Iinv','Iinv-']

    @staticmethod
    def setup(ga):
        """
        Set up constant multivectors required for multivector class for
        a given geometric algebra, `ga`.
        """
        Mv.fmt = 1
        # copy basis in case the caller wanted to change it
        return ga.mv_I, list(ga.mv_basis), ga.mv_x

    @staticmethod
    def Format(mode=1):
        Mv.latex_flg = True
        Mv.fmt = mode

    @staticmethod
    def Mul(A, B, op):
        """
        Function for all types of geometric multiplications called by
        overloaded operators for ``*``, ``^``, ``|``, ``<``, and ``>``.
        """
        if not isinstance(A, Mv):
            A = B.Ga.mv(A)
        if not isinstance(B, Mv):
            B = A.Ga.mv(B)

        if op == '*':
            return A * B
        elif op == '^':
            return A ^ B
        elif op == '|':
            return A | B
        elif op == '<':
            return A < B
        elif op == '>':
            return A > B
        else:
            raise ValueError('Operation ' + op + 'not allowed in Mv.Mul!')

    def characterise_Mv(self):
        if self.char_Mv:
            return
        obj = expand(self.obj)
        if isinstance(obj, numbers.Number):
            self.i_grade = 0
            self.is_blade_rep = True
            self.grades = [0]
            return
        if  obj.is_commutative:
            self.i_grade = 0
            self.is_blade_rep = True
            self.grades = [0]
            return
        if isinstance(obj, Add):
            args = obj.args
        else:
            if obj in self.Ga._all_blades_lst:
                self.is_blade_rep = True
                self.i_grade = self.Ga.blades_to_grades_dict[obj]
                self.grades = [self.i_grade]
                self.char_Mv = True
                self.blade_flg = True
                return
            else:
                args = [obj]

        grades = []
        #print 'args =', args
        self.is_blade_rep = True
        for term in args:
            if term.is_commutative:
                if 0 not in grades:
                    grades.append(0)
            else:
                c, nc = term.args_cnc(split_1=False)
                blade = nc[0]
                #print 'blade =',blade
                if blade in self.Ga._all_blades_lst:
                    grade = self.Ga.blades_to_grades_dict[blade]
                    if not grade in grades:
                        grades.append(grade)
                else:
                    self.char_Mv = True
                    self.is_blade_rep = False
                    self.i_grade = None
                    return
        if len(grades) == 1:
            self.i_grade = grades[0]
        else:
            self.i_grade = None
        self.grades = grades
        self.char_Mv = True

    # helper methods called by __init__. Note that these names must not change,
    # as the part of the name after `_make_` is public API via the string
    # argument passed to __init__.
    #
    # The double underscores in argument names are to force the passing
    # positionally. When python 3.8 is the lowest supported version, we can
    # switch to using the / syntax from PEP570

    @staticmethod
    def _make_grade(ga, __name_or_coeffs, __grade, **kwargs):
        """ Make a pure grade multivector. """
        def add_superscript(root, s):
            if not s:
                return root
            return '{}__{}'.format(root, s)
        grade = __grade
        kw = _KwargParser('_make_grade', kwargs)
        if isinstance(__name_or_coeffs, str):
            name = __name_or_coeffs
            f = kw.pop('f', False)
            kw.reject_remaining()
            if isinstance(f, bool):
                if f:  # Is a multivector function of all coordinates
                    return sum([Function(add_superscript(name, super_script), real=True)(*ga.coords) * base
                                for (super_script, base) in zip(ga.blade_super_scripts[grade], ga.blades[grade])])
                else:  # Is a constant multivector function
                    return sum([Symbol(add_superscript(name, super_script), real=True) * base
                                for (super_script, base) in zip(ga.blade_super_scripts[grade], ga.blades[grade])])
            else:  # Is a multivector function of tuple f variables
                return sum([Function(add_superscript(name, super_script), real=True)(*f) * base
                            for (super_script, base) in zip(ga.blade_super_scripts[grade], ga.blades[grade])])
        elif isinstance(__name_or_coeffs, (list, tuple)):
            coeffs = __name_or_coeffs
            kw.reject_remaining()
            if len(coeffs) <= len(ga.blades[grade]):
                return sum([coef * base
                    for (coef, base) in zip(coeffs, ga.blades[grade][:len(coeffs)])])
            else:
                raise ValueError("Too many coefficients")
        else:
            raise TypeError("Expected a string, list, or tuple")

    @staticmethod
    def _make_scalar(ga, __name_or_value, **kwargs):
        """ Make a scalar multivector """
        if isinstance(__name_or_value, str):
            name = __name_or_value
            return Mv._make_grade(ga, name, 0, **kwargs)
        else:
            value = __name_or_value
            return value

    @staticmethod
    def _make_vector(ga, __name_or_coeffs, **kwargs):
        """ Make a vector multivector """
        return Mv._make_grade(ga, __name_or_coeffs, 1, **kwargs)

    @staticmethod
    def _make_bivector(ga, __name_or_coeffs, **kwargs):
        """ Make a bivector multivector """
        return Mv._make_grade(ga, __name_or_coeffs, 2, **kwargs)

    @staticmethod
    def _make_pseudo(ga, __name_or_coeffs, **kwargs):
        """ Make a pseudo scalar multivector """
        return Mv._make_grade(ga, __name_or_coeffs, ga.n, **kwargs)

    @staticmethod
    def _make_mv(ga, __name, **kwargs):
        """ Make a general (2**n components) multivector """
        if not isinstance(__name, str):
            raise TypeError("Must be a string")
        return reduce(operator.add, (
            Mv._make_grade(ga, __name, grade, **kwargs)
            for grade in range(ga.n + 1)
        ))

    @staticmethod
    def _make_spinor(ga, __name, **kwargs):
        """ Make a general even (spinor) multivector """
        if not isinstance(__name, str):
            raise TypeError("Must be a string")
        return reduce(operator.add, (
            Mv._make_grade(ga, __name, grade, **kwargs)
            for grade in range(0, ga.n + 1, 2)
        ))

    @staticmethod
    def _make_odd(ga, __name, **kwargs):
        """ Make a general odd multivector """
        if not isinstance(__name, str):
            raise TypeError("Must be a string")
        return reduce(operator.add, (
            Mv._make_grade(ga, __name, grade, **kwargs)
            for grade in range(1, ga.n + 1, 2)
        ), S(0))  # base case needed in case n == 0

    # aliases
    _make_grade2 = _make_bivector
    _make_even = _make_spinor

    def __init__(self, *args, ga, recp=None, coords=None, **kwargs):
        """
        __init__(self, *args, ga, recp=None, **kwargs)

        Note this constructor is overloaded, based on the type and number of
        positional arguments:

        .. class:: Mv(*, ga, recp=None)

            Create a zero multivector
        .. class:: Mv(expr, /, *, ga, recp=None)

            Create a multivector from an existing vector or sympy expression
        .. class:: Mv(coeffs, grade, /, ga, recp=None)

            Create a multivector constant with a given grade
        .. class:: Mv(name, category, /, *cat_args, ga, recp=None, f=False)

            Create a multivector constant with a given category
        .. class:: Mv(name, grade, /, ga, recp=None, f=False)

            Create a multivector variable or function of a given grade
        .. class:: Mv(coeffs, category, /, *cat_args, ga, recp=None)

            Create a multivector variable or function of a given category


        ``*`` and ``/`` in the signatures above are python
        3.8 syntax, and respectively indicate the boundaries between
        positional-only, normal, and keyword-only arguments.

        Parameters
        ----------
        ga : ~galgebra.ga.Ga
            Geometric algebra to be used with multivectors
        recp : object, optional
            Normalization for reciprocal vector. Unused.
        name : str
            Name of this multivector, if it is a variable or function
        coeffs : sequence
            Sequence of coefficients for the given category.
            This is only meaningful
        category : str
            One of:

             * ``"grade"`` - this takes an additional argument, the grade to
               create, in ``cat_args``
             * ``"scalar"``
             * ``"vector"``
             * ``"bivector"`` / ``"grade2"``
             * ``"pseudo"``
             * ``"mv"``
             * ``"even"`` / ``"spinor"``
             * ``"odd"``

        f : bool, tuple
            True if function of coordinates, or a tuple of those coordinates.
            Only valid if a name is passed

        coords :
            This argument is always accepted but ignored.

            It is incorrectly described internally as the coordinates to be
            used with multivector functions.
        """
        kw = _KwargParser('__init__', kwargs)
        self.Ga = ga
        self.recp = recp  # not used

        self.char_Mv = False
        self.i_grade = None  # if pure grade mv, grade value
        self.grades = None  # list of grades in mv
        self.is_blade_rep = True  # flag for blade representation
        self.blade_flg = None  # if is_blade is called flag is set
        self.versor_flg = None  # if is_versor is called flag is set
        self.coords = self.Ga.coords
        self.title = None

        if len(args) == 0:  # default constructor 0
            self.obj = S(0)
            self.i_grade = 0
            kw.reject_remaining()
        elif len(args) == 1 and not isinstance(args[0], str):  # copy constructor
            x = args[0]
            if isinstance(x, Mv):
                self.obj = x.obj
                self.is_blade_rep = x.is_blade_rep
                self.i_grade = x.i_grade
            else:
                if isinstance(x, Expr):  #copy constructor for obj expression
                    self.obj = x
                else:  #copy constructor for scalar obj expression
                    self.obj = S(x)
                self.is_blade_rep = True
                self.characterise_Mv()
            kw.reject_remaining()
        else:
            if isinstance(args[1], str):
                make_args = list(args)
                mode = make_args.pop(1)
                make_func = getattr(Mv, '_make_{}'.format(mode), None)
                if make_func is None:
                    raise ValueError('{!r} is not an allowed multivector type.'.format(mode))
                self.obj = make_func(self.Ga, *make_args, **kwargs)
            elif isinstance(args[1], int):  # args[1] = r (integer) Construct grade r multivector
                if args[1] == 0:
                    # _make_scalar interprets its coefficient argument differently
                    make_args = list(args)
                    make_args.pop(1)
                    self.obj = Mv._make_scalar(self.Ga, *make_args, **kwargs)
                else:
                    self.obj = Mv._make_grade(self.Ga, *args, **kwargs)
            else:
                raise TypeError("Expected string or int")

            if isinstance(args[0], str):
                self.title = args[0]
            self.characterise_Mv()

    ################# Multivector member functions #####################

    def reflect_in_blade(self, blade):  # Reflect mv in blade
        # See Mv class functions documentation
        if blade.is_blade():
            self.characterise_Mv()
            blade.characterise_Mv()
            blade_inv = blade.rev() / blade.norm2()
            grade_dict = self.Ga.grade_decomposition(self)
            blade_grade = blade.i_grade
            reflect = Mv(0,'scalar',ga=self.Ga)
            for grade in list(grade_dict.keys()):
                if (grade * (blade_grade + 1)) % 2 == 0:
                    reflect += blade * grade_dict[grade] * blade_inv
                else:
                    reflect -= blade * grade_dict[grade] * blade_inv
            return reflect
        else:
            raise ValueError(str(blade) + 'is not a blade in reflect_in_blade(self, blade)')

    def project_in_blade(self,blade):
        # See Mv class functions documentation
        if blade.is_blade():
            blade.characterise_Mv()
            blade_inv = blade.rev() / blade.norm2()
            return (self < blade) * blade_inv  # < is left contraction
        else:
            raise ValueError(str(blade) + 'is not a blade in project_in_blade(self, blade)')

    def rotate_multivector(self,itheta,hint='-'):
        Rm = (-itheta/S(2)).exp(hint)
        Rp = (itheta/S(2)).exp(hint)
        return Rm * self * Rp

    def base_rep(self):
        """ Express as a linear combination of geometric products """
        if not self.is_blade_rep:
            return self

        b = copy.copy(self)
        b.obj = self.Ga.blade_to_base_rep(self.obj)
        b.is_blade_rep = False
        return b

    def blade_rep(self):
        """ Express as a linear combination of blades """
        if self.is_blade_rep:
            return self

        b = copy.copy(self)
        b.obj = self.Ga.base_to_blade_rep(self.obj)
        b.is_blade_rep = True
        return b

    def __hash__(self):
        if self.is_scalar():
            # ensure we match equality
            return hash(self.obj)
        else:
            return hash((self.Ga, self.obj))

    def __eq__(self, A):
        if isinstance(A, Mv):
            diff = (self - A).expand().simplify()
            #diff = (self - A).expand()
            if diff.obj == S(0):
                return True
            else:
                return False
        else:
            if self.is_scalar() and self.obj == A:
                return True
            else:
                return False

    """
    def __eq__(self, A):
        if not isinstance(A, Mv):
            if not self.is_scalar():
                return False
            if expand(self.obj) == expand(A):
                return True
            else:
                return False
        if self.is_blade_rep != A.is_blade_rep:
            self = self.blade_rep()
            A = A.blade_rep()
        coefs, bases = metric.linear_expand(self.obj)
        Acoefs, Abases = metric.linear_expand(A.obj)
        if len(bases) != len(Abases):
            return False
        if set(bases) != set(Abases):
            return False
        for base in bases:
            index = bases.index(base)
            indexA = Abases.index(base)
            if expand(coefs[index]) != expand(Acoefs[index]):
                return False
        return True
    """

    def __neg__(self):
        return Mv(-self.obj, ga=self.Ga)

    def __add__(self, A):
        if isinstance(A, Dop):
            return NotImplemented

        if not isinstance(A, Mv):
            return Mv(self.obj + A, ga=self.Ga)

        if self.Ga != A.Ga:
            raise ValueError('In + operation Mv arguments are not from same geometric algebra')

        if self.is_blade_rep == A.is_blade_rep:
            return Mv(self.obj + A.obj, ga=self.Ga)
        else:
            if self.is_blade_rep:
                A = A.blade_rep()
            else:
                self = self.blade_rep()
            return Mv(self.obj + A.obj, ga=self.Ga)

    def __radd__(self, A):
        return(self + A)

    def __sub__(self, A):
        if isinstance(A, Dop):
            return NotImplemented

        if self.Ga != A.Ga:
            raise ValueError('In - operation Mv arguments are not from same geometric algebra')

        if self.is_blade_rep == A.is_blade_rep:
            return Mv(self.obj - A.obj, ga=self.Ga)
        else:
            if self.is_blade_rep:
                A = A.blade_rep()
            else:
                self = self.blade_rep()
            return Mv(self.obj - A.obj, ga=self.Ga)

    def __rsub__(self, A):
        return -self + A

    def __mul__(self, A):
        if isinstance(A, Dop):
            return NotImplemented

        if not isinstance(A, Mv):
            return Mv(expand(A * self.obj), ga=self.Ga)

        if self.Ga != A.Ga:
            raise ValueError('In * operation Mv arguments are not from same geometric algebra')

        if self.is_scalar():
            return Mv(self.obj * A, ga=self.Ga)

        if self.is_blade_rep and A.is_blade_rep:
            self = self.base_rep()
            A = A.base_rep()

            selfxA = Mv(self.Ga.mul(self.obj, A.obj), ga=self.Ga)
            selfxA.is_blade_rep = False
            return selfxA.blade_rep()

        elif self.is_blade_rep:
            self = self.base_rep()

            selfxA = Mv(self.Ga.mul(self.obj, A.obj), ga=self.Ga)
            selfxA.is_blade_rep = False
            return selfxA.blade_rep()

        elif A.is_blade_rep:
            A = A.base_rep()

            selfxA = Mv(self.Ga.mul(self.obj, A.obj), ga=self.Ga)
            selfxA.is_blade_rep = False
            return selfxA.blade_rep()
        else:
            return Mv(self.Ga.mul(self.obj, A.obj), ga=self.Ga)


    def __rmul__(self, A):
        if isinstance(A, Dop):
            return NotImplemented
        return Mv(expand(A * self.obj), ga=self.Ga)

    def __truediv__(self, A):
        if isinstance(A, Mv):
            return self * A.inv()
        else:
            return self * (S(1)/A)

    def __str__(self):
        if printer.GaLatexPrinter.latex_flg:
            Printer = printer.GaLatexPrinter
        else:
            Printer = printer.GaPrinter
        return Printer().doprint(self)

    def __repr__(self):
        return str(self)

    def __getitem__(self,key):
        '''
        get a specified grade of a multivector
        '''
        return self.grade(key)

    def Mv_str(self):
        global print_replace_old, print_replace_new
        if self.i_grade == 0:
            return str(self.obj)

        # note: this just replaces `self` for the rest of this function
        obj = expand(self.obj)
        obj = metric.Simp.apply(obj)
        self = Mv(obj, ga=self.Ga)

        if self.is_blade_rep or self.Ga.is_ortho:
            base_keys = self.Ga._all_blades_lst
            grade_keys = self.Ga.blades_to_grades_dict
        else:
            base_keys = self.Ga._all_bases_lst
            grade_keys = self.Ga.bases_to_grades_dict
        if isinstance(self.obj, Add):  # collect coefficients of bases
            if self.obj.is_commutative:
                return self.obj
            args = self.obj.args
            terms = {}  # dictionary with base indexes as keys
            grade0 = S(0)
            for arg in args:
                c, nc = arg.args_cnc()
                c = reduce(operator.mul, c, S(1))
                if len(nc) > 0:
                    base = nc[0]
                    if base in base_keys:
                        index = base_keys.index(base)
                        if index in terms:
                            (c_tmp, base, g_keys) = terms[index]
                            terms[index] = (c_tmp + c, base, g_keys)
                        else:
                            terms[index] = (c, base, grade_keys[base])
                else:
                    grade0 += c
            if grade0 != S(0):
                terms[-1] = (grade0, S(1), -1)
            terms = list(terms.items())
            sorted_terms = sorted(terms, key=operator.itemgetter(0))  # sort via base indexes

            s = str(sorted_terms[0][1][0] * sorted_terms[0][1][1])
            if printer.GaPrinter.fmt == 3:
                s = ' ' + s + '\n'
            if printer.GaPrinter.fmt == 2:
                s = ' ' + s
            old_grade = sorted_terms[0][1][2]
            for (key, (c, base, grade)) in sorted_terms[1:]:
                term = str(c * base)
                if printer.GaPrinter.fmt == 2 and old_grade != grade:  # one grade per line
                    old_grade = grade
                    s += '\n'
                if term[0] == '-':
                    term = ' - ' + term[1:]
                else:
                    term = ' + ' + term
                if printer.GaPrinter.fmt == 3:  # one base per line
                    s += term + '\n'
                else:  # one multivector per line
                    s += term
            if s[-1] == '\n':
                s = s[:-1]
            if printer.print_replace_old is not None:
                s = s.replace(printer.print_replace_old,printer.print_replace_new)
            return s
        else:
            return str(self.obj)

    def Mv_latex_str(self):

        if self.obj == 0:
            return ZERO_STR

        first_line = True

        def append_plus(c_str):
            nonlocal first_line
            if first_line:
                first_line = False
                return c_str
            else:
                c_str = c_str.strip()
                if c_str[0] == '-':
                    return ' ' + c_str
                else:
                    return ' + ' + c_str

        # str representation of multivector
        # note: this just replaces `self` for the rest of this function
        obj = expand(self.obj)
        obj = metric.Simp.apply(obj)
        self = Mv(obj, ga=self.Ga)

        if self.obj == S(0):
            return ZERO_STR

        if self.is_blade_rep or self.Ga.is_ortho:
            base_keys = self.Ga._all_blades_lst
            grade_keys = self.Ga.blades_to_grades_dict
        else:
            base_keys = self.Ga._all_bases_lst
            grade_keys = self.Ga.bases_to_grades_dict
        if isinstance(self.obj, Add):
            args = self.obj.args
        else:
            args = [self.obj]
        terms = {}  # dictionary with base indexes as keys
        grade0 = S(0)
        for arg in args:
            c, nc = arg.args_cnc(split_1=False)
            c = reduce(operator.mul, c, S(1))
            if len(nc) > 0:
                base = nc[0]
                if base in base_keys:
                    index = base_keys.index(base)
                    if index in terms:
                        (c_tmp, base, g_keys) = terms[index]
                        terms[index] = (c_tmp + c, base, g_keys)
                    else:
                        terms[index] = (c, base, grade_keys[base])
            else:
                grade0 += c
        if grade0 != S(0):
            terms[-1] = (grade0, S(1), 0)
        terms = list(terms.items())

        sorted_terms = sorted(terms, key=operator.itemgetter(0))  # sort via base indexes

        if len(sorted_terms) == 1 and sorted_terms[0][1][2] == 0:  # scalar
            return printer.latex(printer.coef_simplify(sorted_terms[0][1][0]))

        lines = []
        old_grade = -1
        s = ''
        for (index, (coef, base, grade)) in sorted_terms:
            coef = printer.coef_simplify(coef)
            #coef = simplify(coef)
            l_coef = printer.latex(coef)
            if l_coef == '1' and base != S(1):
                l_coef = ''
            if l_coef == '-1' and base != S(1):
                l_coef = '-'
            if base == S(1):
                l_base = ''
            else:
                l_base = printer.latex(base)
            if isinstance(coef, Add):
                cb_str = '\\left ( ' + l_coef + '\\right ) ' + l_base
            else:
                cb_str = l_coef + ' ' + l_base
            if printer.GaLatexPrinter.fmt == 3:  # One base per line
                lines.append(append_plus(cb_str))
            elif printer.GaLatexPrinter.fmt == 2:  # One grade per line
                if grade != old_grade:
                    old_grade = grade
                    if not first_line:
                        lines.append(s)
                    s = append_plus(cb_str)
                else:
                    s += append_plus(cb_str)
            else:  # One multivector per line
                s += append_plus(cb_str)
        if printer.GaLatexPrinter.fmt == 2:
            lines.append(s)
        if printer.GaLatexPrinter.fmt >= 2:
            if len(lines) == 1:
                return lines[0]
            s = ' \\begin{align*} '
            for line in lines:
                s += ' & ' + line + ' \\\\ '
            s = s[:-3] + ' \\end{align*} \n'
        return s

    def __xor__(self, A):  # wedge (^) product
        if isinstance(A, Dop):
            return NotImplemented

        if not isinstance(A, Mv):
            return Mv(A * self.obj, ga=self.Ga)

        if self.Ga != A.Ga:
            raise ValueError('In ^ operation Mv arguments are not from same geometric algebra')

        if self.is_scalar():
            return self * A

        self = self.blade_rep()
        A = A.blade_rep()
        return Mv(self.Ga.wedge(self.obj, A.obj), ga=self.Ga)

    def __rxor__(self, A):  # wedge (^) product
        if isinstance(A, Dop):
            return NotImplemented
        assert not isinstance(A, Mv)
        return Mv(A * self.obj, ga=self.Ga)

    def __or__(self, A):  # dot (|) product
        if isinstance(A, Dop):
            return NotImplemented

        if not isinstance(A, Mv):
            return Mv(ga=self.Ga)

        if self.Ga != A.Ga:
            raise ValueError('In | operation Mv arguments are not from same geometric algebra')

        self = self.blade_rep()
        A = A.blade_rep()
        return Mv(self.Ga.hestenes_dot(self.obj, A.obj), ga=self.Ga)

    def __ror__(self, A):  # dot (|) product
        if isinstance(A, Dop):
            return NotImplemented
        assert not isinstance(A, Mv)
        return Mv(ga=self.Ga)

    def __pow__(self,n):  # Integer power operator
        if not isinstance(n,int):
            raise ValueError('!!!!Multivector power can only be to integer power!!!!')

        result = S(1)
        for x in range(n):
            result *= self
        return result

    def __lshift__(self, A): # anti-comutator (<<)
        return half * (self * A + A * self)

    def __rshift__(self, A): # comutator (>>)
        return half * (self * A - A * self)

    def __rlshift__(self, A): # anti-comutator (<<)
        return half * (A * self + self * A)

    def __rrshift__(self, A): # comutator (>>)
        return half * (A * self - self * A)

    def __lt__(self, A):  # left contraction (<)
        if isinstance(A, Dop):
            # Cannot return `NotImplemented` here, as that would call `A > self`
            return A.Mul(self, A, op='<')

        if not isinstance(A, Mv):  # sympy scalar
            return Mv(A * self.obj, ga=self.Ga)

        if self.Ga != A.Ga:
            raise ValueError('In < operation Mv arguments are not from same geometric algebra')

        self = self.blade_rep()
        A = A.blade_rep()
        return Mv(self.Ga.left_contract(self.obj, A.obj), ga=self.Ga)

    def __gt__(self, A):  # right contraction (>)
        if isinstance(A, Dop):
            # Cannot return `NotImplemented` here, as that would call `A < self`
            return A.Mul(self, A, op='>')

        if not isinstance(A, Mv):  # sympy scalar
            return self.Ga.mv(A * self.scalar())

        if self.Ga != A.Ga:
            raise ValueError('In > operation Mv arguments are not from same geometric algebra')

        self = self.blade_rep()
        A = A.blade_rep()
        return Mv(self.Ga.right_contract(self.obj, A.obj), ga=self.Ga)

    def collect(self,deep=False):
        """
        group coeffients of blades of multivector
        so there is only one coefficient per grade
        """
        """ # dead code
        self.obj = expand(self.obj)
        if self.is_blade_rep or Mv.Ga.is_ortho:
            c = self.Ga.blades_lst
        else:
            c = self.Ga.bases_lst
        self.obj = self.obj.collect(c)
        return self
        """
        obj_dict = {}
        for coef, base in metric.linear_expand_terms(self.obj):
            if base in list(obj_dict.keys()):
                obj_dict[base] += coef
            else:
                obj_dict[base] = coef
        obj = S(0)
        for base in list(obj_dict.keys()):
            if deep:
                obj += collect(obj_dict[base])*base
            else:
                obj += obj_dict[base]*base
        return Mv(obj, ga=self.Ga)


    def is_scalar(self):
        grades = self.Ga.grades(self.obj)
        if len(grades) == 1 and grades[0] == 0:
            return True
        else:
            return False

    def is_vector(self):
        grades = self.Ga.grades(self.obj)
        if len(grades) == 1 and grades[0] == 1:
            return True
        else:
            return False

    def is_blade(self):
        """
        True is self is blade, otherwise False
        sets self.blade_flg and returns value
        """
        if self.blade_flg is not None:
            return self.blade_flg
        else:
            if self.is_versor():
                if self.i_grade is not None:
                    self.blade_flg = True
                else:
                    self.blade_flg = False
            else:
                self.blade_flg = False
            return self.blade_flg

    def is_base(self):
        (coefs, _bases) = metric.linear_expand(self.obj)
        if len(coefs) > 1:
            return False
        else:
            return coefs[0] == ONE

    def is_versor(self):
        """
        Test for versor (geometric product of vectors)

        This follows Leo Dorst's test for a versor.
        Leo Dorst, 'Geometric Algebra for Computer Science,' p.533
        Sets self.versor_flg and returns value
        """

        if self.versor_flg is not None:
            return self.versor_flg
        self.characterise_Mv()
        self.versor_flg = False
        self_rev = self.rev()
        # see if self*self.rev() is a scalar
        test = self*self_rev
        if not test.is_scalar():
            return self.versor_flg
        # see if self*x*self.rev() returns a vector for x an arbitrary vector
        test = self * self.Ga._XOX * self.rev()
        self.versor_flg = test.is_vector()
        return self.versor_flg

    def is_zero(self):
        if self.obj == 0:
            return True
        return False

    def scalar(self):
        """ return scalar part of multivector as sympy expression """
        return self.Ga.scalar_part(self.obj)

    def get_grade(self, r):
        """ return r-th grade of multivector as a multivector """
        return Mv(self.Ga.get_grade(self.obj, r), ga=self.Ga)

    def components(self):
        cb = metric.linear_expand_terms(self.obj)
        cb = sorted(cb, key=lambda x: self.Ga._all_blades_lst.index(x[1]))
        return [self.Ga.mv(coef * base) for (coef, base) in cb]

    def get_coefs(self, grade):
        cb = metric.linear_expand_terms(self.obj)
        cb = sorted(cb, key=lambda x: self.Ga.blades[grade].index(x[1]))
        (coefs, bases) = list(zip(*cb))
        return coefs

    def blade_coefs(self, blade_lst=None):
        """
        For a multivector, A, and a list of basis blades, blade_lst return
        a list (sympy expressions) of the coefficients of each basis blade
        in blade_lst
        """

        if blade_lst is None:
            blade_lst = self.Ga._all_mv_blades_lst

        #print 'Enter blade_coefs blade_lst =', blade_lst, type(blade_lst), [i.is_blade() for i in blade_lst]

        for blade in blade_lst:
            if not blade.is_base() or not blade.is_blade():
                raise ValueError("%s expression isn't a basis blade" % blade)
        blade_lst = [x.obj for x in blade_lst]
        (coefs, bases) = metric.linear_expand(self.obj)
        coef_lst = []
        for blade in blade_lst:
            if blade in bases:
                coef_lst.append(coefs[bases.index(blade)])
            else:
                coef_lst.append(ZERO)
        return coef_lst

    def proj(self, bases_lst):
        """
        Project multivector onto a given list of bases.  That is find the
        part of multivector with the same bases as in the bases_lst.
        """
        bases_lst = [x.obj for x in bases_lst]
        obj = 0
        for coef, base in metric.linear_expand_terms(self.obj):
            if base in bases_lst:
                obj += coef * base
        return Mv(obj, ga=self.Ga)

    def dual(self):
        mode = self.Ga.dual_mode_value
        sign = S(1)
        if '-' in mode:
            sign = -sign
        if 'Iinv' in mode:
            I = self.Ga.i_inv
        else:
            I = self.Ga.i
        if mode[0] == '+' or mode[0] == '-':
            return sign * I * self
        else:
            return sign * self * I

    def even(self):
        """ return even parts of multivector """
        return Mv(self.Ga.even_odd(self.obj, True), ga=self.Ga)

    def odd(self):
        """ return odd parts of multivector """
        return Mv(self.Ga.even_odd(self.obj, False), ga=self.Ga)

    def rev(self):
        self = self.blade_rep()
        return Mv(self.Ga.reverse(self.obj), ga=self.Ga)

    __invert__ = rev # allow `~x` to call x.rev()

    def diff(self, coord):
        if self.Ga.coords is None:
            obj = diff(self.obj, coord)
        elif coord not in self.Ga.coords:
            if self.Ga.par_coords is None:
                obj = diff(self.obj, coord)
            elif coord not in self.Ga.par_coords:
                obj = diff(self.obj, coord)
            else:
                obj = diff(self.obj, coord)
                for x_coord in self.Ga.coords:
                    f = self.Ga.par_coords[x_coord]
                    if f != S(0):
                        tmp1 = self.Ga.pDiff(self.obj, x_coord)
                        tmp2 = diff(f, coord)
                        obj += tmp1 * tmp2
        else:
            obj = self.Ga.pDiff(self.obj, coord)
        return Mv(obj, ga=self.Ga)

    def pdiff(self, var):
        return Mv(self.Ga.pDiff(self.obj, var), ga=self.Ga)

    def Grad(self, coords, mode='*', left=True):
        """
        Returns various derivatives (*,^,|,<,>) of multivector functions
        with respect to arbitrary coordinates, 'coords'.  This would be
        used where you have a multivector function of both the basis
        coordinate set and and auxiliary coordinate set.  Consider for
        example a linear transformation in which the matrix coefficients
        depend upon the manifold coordinates, but the vector being
        transformed does not and you wish to take the divergence of the
        linear transformation with respect to the linear argument.
        """
        return Mv(self.Ga.Diff(self, mode, left, coords=coords), ga=self.Ga)

    def exp(self, hint='-'):  # Calculate exponential of multivector
        """
        Only works if square of multivector is a scalar.  If square is a
        number we can determine if square is > or < zero and hence if
        one should use trig or hyperbolic functions in expansion.  If
        square is not a number use 'hint' to determine which type of
        functions to use in expansion
        """
        self = self.blade_rep()
        self_sq = self * self
        if self_sq.is_scalar():
            sq = simplify(self_sq.obj)  # sympy expression for self**2
            if sq == S(0):  # sympy expression for self**2 = 0
                return self + S(1)
            (coefs,bases) = metric.linear_expand(self.obj)
            if len(coefs) == 1:  # Exponential of scalar * base
                base = bases[0]
                base_Mv = self.Ga.mv(base)
                base_sq = (base_Mv*base_Mv).scalar()
                if hint == '-': # base^2 < 0
                    base_n = sqrt(-base_sq)
                    return self.Ga.mv(cos(base_n*coefs[0]) + sin(base_n*coefs[0])*(bases[0]/base_n))
                else:  # base^2 > 0
                    base_n = sqrt(base_sq)
                    return self.Ga.mv(cosh(base_n*coefs[0]) + sinh(base_n*coefs[0])*(bases[0]/base_n))
            if sq.is_number:  # Square is number, can test for sign
                if sq > S(0):
                    norm = sqrt(sq)
                    value = self.obj / norm
                    tmp = Mv(cosh(norm) + sinh(norm) * value, ga=self.Ga)
                    tmp.is_blade_rep = True
                    return tmp
                else:
                    norm = sqrt(-sq)
                    value = self.obj / norm
                    tmp = Mv(cos(norm) + sin(norm) * value, ga=self.Ga)
                    tmp.is_blade_rep = True
                    return tmp
            else:
                if hint == '+':
                    norm = simplify(sqrt(sq))
                    value = self.obj / norm
                    tmp = Mv(cosh(norm) + sinh(norm) * value, ga=self.Ga)
                    tmp.is_blade_rep = True
                    return tmp
                else:
                    norm = simplify(sqrt(-sq))
                    value = self.obj / norm
                    obj = cos(norm) + sin(norm) * value
                    tmp = Mv(cos(norm) + sin(norm) * value, ga=self.Ga)
                    tmp.is_blade_rep = True
                    return tmp
        else:
            raise ValueError('"' + str(self) + '**2" is not a scalar in exp.')

    def set_coef(self, igrade, ibase, value):
        if self.blade_rep:
            base = self.Ga.blades[igrade][ibase]
        else:
            base = self.Ga.bases[igrade][ibase]
        (coefs, bases) = metric.linear_expand(self.obj)
        bases_lst = list(bases)  # python 2.5
        if base in bases:
            self.obj += (value - coefs[bases_lst.index(base)]) * base
        else:
            self.obj += value * base

    def Fmt(self, fmt=1, title=None):
        """
        Set format for printing of multivectors

         * `fmt=1` - One multivector per line
         * `fmt=2` - One grade per line
         * `fmt=3` - one base per line

        Usage for multivector ``A`` example is::

            A.Fmt('2','A')

        output is::

            'A = '+str(A)

        with one grade per line.  Works for both standard printing and
        for latex.
        """
        if printer.GaLatexPrinter.latex_flg:
            printer.GaLatexPrinter.prev_fmt = printer.GaLatexPrinter.fmt
            printer.GaLatexPrinter.fmt = fmt
        else:
            printer.GaPrinter.prev_fmt = printer.GaPrinter.fmt
            printer.GaPrinter.fmt = fmt

        if title is not None:
            self.title = title

        if printer.isinteractive():
            return self

        if Mv.latex_flg:
            latex_str = printer.GaLatexPrinter.latex(self)
            printer.GaLatexPrinter.fmt = printer.GaLatexPrinter.prev_fmt

            if title is not None:
                return title + ' = ' + latex_str
            else:
                return latex_str
        else:
            s = str(self)
            printer.GaPrinter.fmt = printer.GaPrinter.prev_fmt
            if title is not None:
                return title + ' = ' + s
            else:
                return s

    def _repr_latex_(self):
        latex_str = printer.GaLatexPrinter.latex(self)
        if r'\begin{align*}' not in latex_str:
            if self.title is None:
                latex_str = r'\begin{equation*} ' + latex_str + r' \end{equation*}'
            else:
                latex_str = r'\begin{equation*} ' + self.title + ' = ' + latex_str + r' \end{equation*}'
        else:
            if self.title is not None:
                latex_str = latex_str.replace('&',' ' + self.title + ' =&',1)
        return latex_str

    def norm2(self):
        reverse = self.rev()
        product = self * reverse
        if product.is_scalar():
            return product.scalar()
        else:
            raise TypeError('"(' + str(product) + ')**2" is not a scalar in norm2.')

    def norm(self, hint='+'):
        """
        If A is a multivector and A*A.rev() is a scalar then::

            A.norm() == sqrt(Abs(A*A.rev()))

        The problem in simplifying the norm is that if ``A`` is symbolic
        you don't know if ``A*A.rev()`` is positive or negative. The use
        of the hint argument is as follows:

        =======  ========================
        hint     ``A.norm()``
        =======  ========================
        ``'+'``  ``sqrt(A*A.rev())``
        ``'-'``  ``sqrt(-A*A.rev())``
        ``'0'``  ``sqrt(Abs(A*A.rev()))``
        =======  ========================

        The default ``hint='+'`` is correct for vectors in a Euclidean vector
        space.  For bivectors in a Euclidean vector space use ``hint='-'``. In
        a mixed signature space all bets are off for the norms of symbolic
        expressions.
        """
        reverse = self.rev()
        product = self * reverse

        if product.is_scalar():
            product = product.scalar()
            if product.is_number:
                if product >= S(0):
                    return sqrt(product)
                else:
                    return sqrt(-product)
            else:
                if hint == '+':
                    return metric.square_root_of_expr(product)
                elif hint == '-':
                    return metric.square_root_of_expr(-product)
                else:
                    return sqrt(Abs(product))
        else:
            raise TypeError('"(' + str(product) + ')" is not a scalar in norm.')

    __abs__ = norm # allow `abs(x)` to call z.norm()

    def inv(self):
        if self.is_scalar():  # self is a scalar
            return self.Ga.mv(S(1)/self.obj)
        self_sq = self * self
        if self_sq.is_scalar():  # self*self is a scalar
            """
            if self_sq.scalar() == S(0):
                raise ValueError('!!!!In multivector inverse, A*A is zero!!!!')
            """
            return (S(1)/self_sq.obj)*self
        self_rev = self.rev()
        self_self_rev = self * self_rev
        if(self_self_rev.is_scalar()): # self*self.rev() is a scalar
            """
            if self_self_rev.scalar() == S(0):
                raise ValueError('!!!!In multivector inverse A*A.rev() is zero!!!!')
            """
            return (S(1)/self_self_rev.obj) * self_rev
        raise TypeError('In inv() for self =' + str(self) + 'self, or self*self or self*self.rev() is not a scalar')

    def func(self, fct):  # Apply function, fct, to each coefficient of multivector
        s = S(0)
        for coef, base in metric.linear_expand_terms(self.obj):
            s += fct(coef) * base
        fct_self = Mv(s, ga=self.Ga)
        fct_self.characterise_Mv()
        return fct_self

    def trigsimp(self):
        return self.func(trigsimp)

    def simplify(self, modes=simplify):
        if not isinstance(modes, (list, tuple)):
            modes = [modes]

        obj = S(0)
        for coef, base in metric.linear_expand_terms(self.obj):
            for mode in modes:
                coef = mode(coef)
            obj += coef * base
        return Mv(obj, ga=self.Ga)

    def subs(self, d):
        # For each scalar coef of the multivector apply substitution argument d
        obj = sum((
            coef.subs(d) * base for coef, base in metric.linear_expand_terms(self.obj)
        ), S(0))
        return Mv(obj, ga=self.Ga)

    def expand(self):
        obj = sum((
            expand(coef) * base for coef, base in metric.linear_expand_terms(self.obj)
        ), S(0))
        return Mv(obj, ga=self.Ga)

    def list(self):
        indexes = []
        key_coefs = []
        for coef, base in metric.linear_expand_terms(self.obj):
            if base in self.Ga.basis:
                index = self.Ga.basis.index(base)
                key_coefs.append((coef, index))
                indexes.append(index)

        for index in self.Ga.n_range:
            if index not in indexes:
                key_coefs.append((S(0), index))

        key_coefs = sorted(key_coefs, key=operator.itemgetter(1))
        coefs = [x[0] for x in key_coefs]
        return coefs

    def grade(self, r=0):
        return self.get_grade(r)

    def pure_grade(self):
        """
        For pure grade return grade.  If not pure grade return negative
        of maximum grade
        """
        self.characterise_Mv()
        if self.i_grade is not None:
            return self.i_grade
        return -self.grades[-1]


def compare(A,B):
    """
    Determine if ``B = c*A`` where c is a scalar.  If true return c
    otherwise return 0.
    """
    if isinstance(A, Mv) and isinstance(B, Mv):
        Acoefs, Abases = metric.linear_expand(A.obj)
        Bcoefs, Bbases = metric.linear_expand(B.obj)
        if len(Acoefs) != len(Bcoefs):
            return 0
        if Abases != Bbases:
            return 0
        if Bcoefs[0] != 0 and Abases[0] == Bbases[0]:
            c = simplify(Acoefs[0]/Bcoefs[0])
            print('c =',c)
        else:
            return 0
        for acoef,abase,bcoef,bbase in zip(Acoefs[1:],Abases[1:],Bcoefs[1:],Bbases[1:]):
            print(acoef,'\n',abase,'\n',bcoef,'\n',bbase)
            if bcoef != 0 and abase == bbase:
                print('c-a/b =',simplify(c-(acoef/bcoef)))
                if simplify(acoef/bcoef) != c:
                    return 0
                else:
                    pass
            else:
                return 0
        return c
    else:
        raise TypeError('In compare both arguments are not multivectors\n')

################# Multivector Differential Operator Class ##############

class Dop(object):
    r"""
    Differential operator class for multivectors.  The operators are of
    the form

    .. math:: D = D^{i_{1}...i_{n}}\partial_{i_{1}...i_{n}}

    where the :math:`D^{i_{1}...i_{n}}` are multivector functions of the coordinates
    :math:`x_{1},...,x_{n}` and :math:`\partial_{i_{1}...i_{n}}` are partial derivative
    operators

    .. math:: \partial_{i_{1}...i_{n}} =
            \frac{\partial^{i_{1}+...+i_{n}}}{\partial{x_{1}^{i_{1}}}...\partial{x_{n}^{i_{n}}}}.

    If :math:`*` is any multivector multiplicative operation then the operator D
    operates on the multivector function :math:`F` by the following definitions

    .. math:: D*F = D^{i_{1}...i_{n}}*\partial_{i_{1}...i_{n}}F

    returns a multivector and

    .. math:: F*D = F*D^{i_{1}...i_{n}}\partial_{i_{1}...i_{n}}

    returns a differential operator.  If the :attr:`cmpflg` in the operator is
    set to ``True`` the operation returns

    .. math:: F*D = (\partial_{i_{1}...i_{n}}F)*D^{i_{1}...i_{n}}

    a multivector function.  For example the representation of the grad
    operator in 3d would be:

    .. math::
        D^{i_{1}...i_{n}} &= [e_x,e_y,e_z] \\
        \partial_{i_{1}...i_{n}} &= [(1,0,0),(0,1,0),(0,0,1)].

    See LaTeX documentation for definitions of operator algebraic
    operations ``+``, ``-``, ``*``, ``^``, ``|``, ``<``, and ``>``.

    Attributes
    ----------
    ga : ~galgebra.ga.Ga
        Associated geometric algebra
    cmpflg : bool
        Complement flag
    terms : list of tuples
    """

    def __init__(self, *args, ga, cmpflg=False, debug=False, fmt_dop=1):
        """
        Parameters
        ----------
        ga :
            Associated geometric algebra
        cmpflg : bool
            Complement flag for Dop
        debug : bool
            True to print out debugging information
        fmt_dop :
            1 for normal dop partial derivative formatting
        """

        self.cmpflg = cmpflg
        self.Ga = ga

        if self.Ga is None:
            raise ValueError('In Dop.__init__ self.Ga must be defined.')

        self.dop_fmt = fmt_dop
        self.title = None

        if len(args) == 2:
            coefs, pdiffs = args
            if len(coefs) != len(pdiffs):
                raise ValueError('In Dop.__init__ coefficent list and Pdop list must be same length.')
            self.terms = tuple(zip(coefs, pdiffs))
        elif len(args) == 1:
            arg, = args
            if len(arg) == 0:
                self.terms = ()
            elif isinstance(arg[0][0], Mv):  # Mv expansion [(Mv, Pdop)]
                self.terms = tuple(arg)
            elif isinstance(arg[0][0], dop.Sdop):  # Sdop expansion [(Sdop, Mv)]
                self.terms = dop._consolidate_terms(
                    (coef * mv, pdiff)
                    for (sdop, mv) in arg
                    for (coef, pdiff) in sdop.terms
                )
            else:
                raise ValueError('In Dop.__init__ args[0] form not allowed. args = ' + str(args))
        else:
            raise ValueError('In Dop.__init__ length of args must be 1 or 2.')


    def simplify(self, modes=simplify):
        """
        Simplify each multivector coefficient of a partial derivative
        """
        return Dop(
            [(coef.simplify(modes=modes), pd) for coef, pd in self.terms],
            ga=self.Ga, cmpflg=self.cmpflg
        )

    def consolidate_coefs(self):
        """
        Remove zero coefs and consolidate coefs with repeated pdiffs.
        """
        return Dop(dop._consolidate_terms(self.terms), ga=self.Ga, cmpflg=self.cmpflg)

    @staticmethod
    def Add(dop1, dop2):

        if isinstance(dop1, Dop) and isinstance(dop2, Dop):
            if dop1.Ga != dop2.Ga:
                raise ValueError('In Dop.Add Dop arguments are not from same geometric algebra')

            if dop1.cmpflg != dop2.cmpflg:
                raise ValueError('In Dop.Add complement flags have different values: %s vs. %s' % (dop1.cmpflg, dop2.cmpflg))

            return Dop(dop._merge_terms(dop1.terms, dop2.terms), cmpflg=dop1.cmpflg, ga=dop1.Ga)
        else:
            # convert values to multiplicative operators
            if isinstance(dop1, Dop):
                if not isinstance(dop2, Mv):
                    dop2 = dop1.Ga.mv(dop2)
                dop2 = Dop([(dop2, dop.Pdop({}))], cmpflg=dop1.cmpflg, ga=dop1.Ga)
            elif isinstance(dop2, Dop):
                if not isinstance(dop1, Mv):
                    dop1 = dop2.Ga.mv(dop1)
                dop1 = Dop([(dop1, dop.Pdop({}))], cmpflg=dop2.cmpflg, ga=dop2.Ga)
            else:
                raise TypeError("Neither argument is a Dop instance")
            return Dop.Add(dop1, dop2)

    def __add__(self, dop):
        return Dop.Add(self, dop)

    def __radd__(self, dop):
        return Dop.Add(dop, self)

    def __neg__(self):
        return Dop(
            [(-coef, pdiff) for coef, pdiff in self.terms],
            ga=self.Ga, cmpflg=self.cmpflg
        )

    def __sub__(self, dop):
        return Dop.Add(self, -dop)

    def __rsub__(self, dop):
        return Dop.Add(dop, -self)

    @staticmethod
    def Mul(dopl, dopr, op='*'):  # General multiplication of Dop's
        # cmpflg is True if the Dop operates on the left argument and
        # False if the Dop operates on the right argument

        if isinstance(dopl, Dop) and isinstance(dopr, Dop):
            if dopl.Ga != dopr.Ga:
                raise ValueError('In Dop.Mul Dop arguments are not from same geometric algebra')
            ga = dopl.Ga
            if dopl.cmpflg != dopr.cmpflg:
                raise ValueError('In Dop.Mul Dop arguments do not have same cmplfg')
            if not dopl.cmpflg:  # dopl and dopr operate on right argument
                terms = []
                for (coef, pdiff) in dopl.terms:  #Apply each dopl term to dopr
                    Ddopl = pdiff(dopr.terms)  # list of terms
                    Ddopl = [(Mv.Mul(coef, c, op=op), p) for c, p in Ddopl]
                    terms += Ddopl
                product = Dop(terms, ga=ga)
            else:  # dopl and dopr operate on left argument
                terms = []
                for (coef, pdiff) in dopr.terms:
                    Ddopr = pdiff(dopl.terms)  # list of terms
                    Ddopr = [(Mv.Mul(c, coef, op=op), p) for c, p in Ddopr]
                    terms += Ddopr
                product = Dop(terms, ga=ga, cmpflg=True)
        else:
            if not isinstance(dopl, Dop):  # dopl is a scalar or Mv and dopr is Dop
                if isinstance(dopl, Mv) and dopl.Ga != dopr.Ga:
                    raise ValueError('In Dop.Mul Dop arguments are not from same geometric algebra')
                else:
                    dopl = dopr.Ga.mv(dopl)
                ga = dopl.Ga

                if not dopr.cmpflg:  # dopr operates on right argument
                    terms = [(Mv.Mul(dopl, coef, op=op), pdiff) for coef, pdiff in dopr.terms]
                    return Dop(terms, ga=ga)  # returns Dop
                else:
                    product = sum([Mv.Mul(pdiff(dopl), coef, op=op) for coef, pdiff in dopr.terms], Mv(0, ga=ga))  # returns multivector
            else:  # dopr is a scalar or a multivector

                if isinstance(dopr, Mv) and dopl.Ga != dopr.Ga:
                    raise ValueError('In Dop.Mul Dop arguments are not from same geometric algebra')
                ga = dopl.Ga

                if not dopl.cmpflg:  # dopl operates on right argument
                    return sum([Mv.Mul(coef, pdiff(dopr), op=op) for coef, pdiff in dopl.terms], Mv(0, ga=ga))  # returns multivector
                else:
                    terms = [(Mv.Mul(coef, dopr, op=op), pdiff) for coef, pdiff in dopl.terms]
                    product = Dop(terms, ga=dopl.Ga, cmpflg=True)  # returns Dop complement
        if isinstance(product, Dop):
            product = product.consolidate_coefs()
        return product

    def TSimplify(self):
        return Dop([
            (metric.Simp.apply(coef), pdiff) for (coef, pdiff) in self.terms
        ], ga=self.Ga)

    def __truediv__(self, dopr):
        if isinstance(dopr, (Dop, Mv)):
            raise TypeError('In Dop.__truediv__ dopr must be a sympy scalar.')
        return Dop([
            (coef / dopr, pdiff) for (coef, pdiff) in self.terms
        ], ga=self.Ga, cmpflg=self.cmpflg)

    def __mul__(self, dopr):  # * geometric product
        return Dop.Mul(self, dopr, op='*')

    def __rmul__(self, dopl):  # * geometric product
        return Dop.Mul(dopl, self, op='*')

    def __xor__(self, dopr):  # ^ outer product
        return Dop.Mul(self, dopr, op='^')

    def __rxor__(self, dopl):  # ^ outer product
        return Dop.Mul(dopl, self, op='^')

    def __or__(self, dopr):  # | inner product
        return Dop.Mul(self, dopr, op='|')

    def __ror__(self, dopl):  # | inner product
        return Dop.Mul(dopl, self, op='|')

    def __lt__(self, dopr):  # < left contraction
        return Dop.Mul(self, dopr, op='<')

    def __gt__(self, dopr):  # > right contraction
        return Dop.Mul(self, dopr, op='>')

    def __eq__(self, other):
        if isinstance(other, Dop):
            if self.Ga != other.Ga:
                return NotImplemented

            diff = self - other
            return len(diff.terms) == 0
        else:
            return NotImplemented

    def __str__(self):
        if printer.GaLatexPrinter.latex_flg:
            Printer = printer.GaLatexPrinter
        else:
            Printer = printer.GaPrinter

        return Printer().doprint(self)

    def __repr__(self):
        return str(self)

    def _repr_latex_(self):
        latex_str = printer.GaLatexPrinter.latex(self)
        if r'\begin{align*}' not in latex_str:
            if self.title is None:
                latex_str = r'\begin{equation*} ' + latex_str + r' \end{equation*}'
            else:
                latex_str = r'\begin{equation*} ' + self.title + ' = ' + latex_str + r' \end{equation*}'
        else:
            if self.title is not None:
                latex_str = latex_str.replace('&',' ' + self.title + ' =&',1)
        return latex_str

    def is_scalar(self):
        for coef, pdiff in self.terms:
            if isinstance(coef, Mv) and not coef.is_scalar():
                return False
        return True

    def components(self):
        return tuple(
            Dop(dop._consolidate_terms(
                (Mv(coef * base, ga=self.Ga), pdiff)
                for (coef, pdiff) in sdop.terms
            ), ga=self.Ga)
            for (sdop, base) in self.Dop_mv_expand()
        )

    def Dop_mv_expand(self, modes=None):
        coefs = []
        bases = []
        self.consolidate_coefs()

        for (coef, pdiff) in self.terms:
            if isinstance(coef, Mv) and not coef.is_scalar():
                for mv_coef, mv_base in metric.linear_expand_terms(coef.obj):
                    if mv_base in bases:
                        index = bases.index(mv_base)
                        coefs[index] += dop.Sdop([(mv_coef, pdiff)])
                    else:
                        bases.append(mv_base)
                        coefs.append(dop.Sdop([(mv_coef, pdiff)]))
            else:
                if isinstance(coef, Mv):
                    mv_coef = coef.obj
                else:
                    mv_coef = coef
                if S(1) in bases:
                    index = bases.index(S(1))
                    coefs[index] += dop.Sdop([(mv_coef, pdiff)])
                else:
                    bases.append(S(1))
                    coefs.append(dop.Sdop([(mv_coef, pdiff)]))
        if modes is not None:
            for i in range(len(coefs)):
                coefs[i] = coefs[i].simplify(modes)
        terms = list(zip(coefs, bases))
        return sorted(terms, key=lambda x: self.Ga._all_blades_lst.index(x[1]))

    def Dop_str(self):
        if len(self.terms) == 0:
            return ZERO_STR

        mv_terms = self.Dop_mv_expand(modes=simplify)
        s = ''

        for (sdop, base) in mv_terms:
            str_base = printer.latex(base)
            str_sdop = printer.latex(sdop)
            if base == S(1):
                s += str_sdop
            else:
                if len(sdop.terms) > 1:
                    if self.cmpflg:
                        s += '(' + str_sdop + ')*' + str_base
                    else:
                        s += str_base + '*(' + str_sdop + ')'
                else:
                    if str_sdop[0] == '-' and not isinstance(sdop.terms[0][0], Add):
                        if self.cmpflg:
                            s += str_sdop + '*' + str_base
                        else:
                            s += '-' + str_base + '*' + str_sdop[1:]
                    else:
                        if self.cmpflg:
                            s += str_sdop + '*' + str_base
                        else:
                            s += str_base + '*' + str_sdop
            s += ' + '

        s = s.replace('+ -','-')
        return s[:-3]

    def Dop_latex_str(self):
        if len(self.terms) == 0:
            return ZERO_STR

        self.consolidate_coefs()

        mv_terms = self.Dop_mv_expand(modes=simplify)
        s = ''

        for (sdop, base) in mv_terms:
            str_base = printer.latex(base)
            str_sdop = printer.latex(sdop)
            if base == S(1):
                s += str_sdop
            else:
                if str_sdop == '1':
                    s += str_base
                if str_sdop == '-1':
                    s += '-' + str_base
                    if str_sdop[1:] != '1':
                        s += ' ' + str_sdop[1:]
                else:
                    if len(sdop.terms) > 1:
                        if self.cmpflg:
                            s += r'\left ( ' + str_sdop + r'\right ) ' + str_base
                        else:
                            s += str_base + ' ' + r'\left ( ' + str_sdop + r'\right ) '
                    else:
                        if str_sdop[0] == '-' and not isinstance(sdop.terms[0][0], Add):
                            if self.cmpflg:
                                s += str_sdop + str_base
                            else:
                                s += '-' + str_base + ' ' + str_sdop[1:]
                        else:
                            if self.cmpflg:
                                s += str_sdop + ' ' + str_base
                            else:
                                s += str_base + ' ' + str_sdop
            s += ' + '

        s = s.replace('+ -','-')
        dop.Sdop.str_mode = False
        return s[:-3]

    def Fmt(self, fmt=1, title=None, dop_fmt=None):
        if printer.GaLatexPrinter.latex_flg:
            printer.GaLatexPrinter.prev_fmt = printer.GaLatexPrinter.fmt
            printer.GaLatexPrinter.prev_dop_fmt = printer.GaLatexPrinter.dop_fmt
        else:
            printer.GaPrinter.prev_fmt = printer.GaPrinter.fmt
            printer.GaPrinter.prev_dop_fmt = printer.GaPrinter.dop_fmt

        if title is not None:
            self.title = title

        if printer.isinteractive():
            return self

        if Mv.latex_flg:
            latex_str = printer.GaLatexPrinter.latex(self)
            printer.GaLatexPrinter.fmt = printer.GaLatexPrinter.prev_fmt
            printer.GaLatexPrinter.dop_fmt = printer.GaLatexPrinter.prev_dop_fmt

            if title is not None:
                return title + ' = ' + latex_str
            else:
                return latex_str
        else:
            s = str(self)
            printer.GaPrinter.fmt = printer.GaPrinter.prev_fmt
            printer.GaPrinter.dop_fmt = printer.GaPrinter.prev_dop_fmt

            if title is not None:
                return title + ' = ' + s
            else:
                return s


################################# Alan Macdonald's additions #########################


def Nga(x, prec=5):
    if isinstance(x, Mv):
        return Mv(Nsympy(x.obj, prec), ga=x.Ga)
    else:
        return Nsympy(x, prec)


def printeigen(M):    # Print eigenvalues, multiplicities, eigenvectors of M.
    evects = M.eigenvects()
    for i in range(len(evects)):                   # i iterates over eigenvalues
        print(('Eigenvalue =', evects[i][0], '  Multiplicity =', evects[i][1], ' Eigenvectors:'))
        for j in range(len(evects[i][2])):         # j iterates over eigenvectors of a given eigenvalue
            result = '['
            for k in range(len(evects[i][2][j])):  # k iterates over coordinates of an eigenvector
                result += str(trigsimp(evects[i][2][j][k]).evalf(3))
                if k != len(evects[i][2][j]) - 1:
                    result += ', '
            result += '] '
            print(result)


def printGS(M, norm=False):  # Print Gram-Schmidt output.
    from sympy import GramSchmidt
    global N
    N = GramSchmidt(M, norm)
    result = '[ '
    for i in range(len(N)):
        result += '['
        for j in range(len(N[0])):
            result += str(trigsimp(N[i][j]).evalf(3))
            if j != len(N[0]) - 1:
                result += ', '
        result += '] '
        if j != len(N[0]) - 1:
            result += ' '
    result += ']'
    print(result)


def printrref(matrix, vars="xyzuvwrs"):   # Print rref of matrix with variables.
    rrefmatrix = matrix.rref()[0]
    rows, cols = rrefmatrix.shape
    if len(vars) < cols - 1:
        print('Not enough variables.')
        return
    for i in range(rows):
        result = ''
        for j in range(cols - 1):
            result += str(rrefmatrix[i, j]) + vars[j]
            if j != cols - 2:
                result += ' + '
        result += ' = ' + str(rrefmatrix[i, cols - 1])
        print(result)


def com(A, B):
    raise ImportError(
        """mv.com is removed, please use galgebra.ga.Ga.com(A, B) instead.""")


def correlation(u, v, dec=3):  # Compute the correlation coefficient of vectors u and v.
    rows, cols = u.shape
    uave = 0
    vave = 0
    for i in range(rows):
        uave += u[i]
        vave += v[i]
    uave = uave / rows
    vave = vave / rows
    ulocal = u[:, :]  # Matrix copy
    vlocal = v[:, :]
    for i in range(rows):
        ulocal[i] -= uave
        vlocal[i] -= vave
    return ulocal.dot(vlocal) / (ulocal.norm() * vlocal.norm()). evalf(dec)


def cross(v1, v2):
    if v1.is_vector() and v2.is_vector() and v1.Ga == v2.Ga and v1.Ga.n == 3:
        return -v1.Ga.I() * (v1 ^ v2)
    else:
        raise ValueError(str(v1) + ' and ' + str(v2) + ' not compatible for cross product.')


def dual(A):
    if isinstance(A, Mv):
        return A.dual()
    else:
        raise ValueError('A not a multivector in dual(A)')


def even(A):
    if not isinstance(A,Mv):
        raise ValueError('A = ' + str(A) + ' not a multivector in even(A).')
    return A.even()


def odd(A):
    if not isinstance(A,Mv):
        raise ValueError('A = ' + str(A) + ' not a multivector in even(A).')
    return A.odd()


def exp(A,hint='-'):
    if isinstance(A,Mv):
        return A.exp(hint)
    else:
        return sympy_exp(A)


def grade(A, r=0):
    if isinstance(A, Mv):
        return A.grade(r)
    else:
        raise ValueError('A not a multivector in grade(A,r)')


def inv(A):
    if not isinstance(A,Mv):
        raise ValueError('A = ' + str(A) + ' not a multivector in inv(A).')
    return A.inv()


def norm(A, hint='+'):
    if isinstance(A, Mv):
        return A.norm(hint=hint)
    else:
        raise ValueError('A not a multivector in norm(A)')


def norm2(A):
    if isinstance(A, Mv):
        return A.norm2()
    else:
        raise ValueError('A not a multivector in norm(A)')


def proj(B, A):  # Project on the blade B the multivector A
    if isinstance(A,Mv):
        return A.project_in_blade(B)
    else:
        raise ValueError('A not a multivector in proj(B,A)')


def rot(itheta, A, hint='-'):  # Rotate by the 2-blade itheta the multivector A
    if isinstance(A,Mv):
        return A.rotate_multivector(itheta, hint)
    else:
        raise ValueError('A not a multivector in rotate(A,itheta)')


def refl(B, A):  #  Project on the blade B the multivector A
    if isinstance(A,Mv):
        return A.reflect_in_blade(B)
    else:
        raise ValueError('A not a multivector in reflect(B,A)')


def rev(A):
    if isinstance(A, Mv):
        return A.rev()
    else:
        raise ValueError('A not a multivector in rev(A)')


def scalar(A):
    if not isinstance(A,Mv):
        raise ValueError('A = ' + str(A) + ' not a multivector in inv(A).')
    return A.scalar()
