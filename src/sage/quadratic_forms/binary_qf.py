"""
Binary Quadratic Forms with Integer Coefficients

This module provides a specialized class for working with a binary quadratic
form `a x^2 + b x y + c y^2`, stored as a triple of integers `(a, b, c)`.

EXAMPLES::

    sage: Q = BinaryQF([1,2,3])
    sage: Q
    x^2 + 2*x*y  + 3*y^2
    sage: Q.discriminant()
    -8
    sage: Q.reduced_form()
    x^2 + 2*y^2
    sage: Q(1, 1)
    6

TESTS::

    sage: Q == loads(dumps(Q))
    True

AUTHORS:

- Jon Hanke (2006-08-08):

  - Appended to add the methods :func:`BinaryQF_reduced_representatives`,
    :meth:`~BinaryQF.is_reduced`, and ``__add__`` on 8-3-2006 for Coding Sprint
    #2.
  - Added Documentation and :meth:`~BinaryQF.complex_point` method on 8-8-2006.

- Nick Alexander: add doctests and clean code for Doc Days 2
- William Stein (2009-08-05): composition; some ReSTification.
- William Stein (2009-09-18): make immutable.
- Justin C. Walker (2011-02-06):
  * Add support for indefinite forms.
"""

#*****************************************************************************
#       Copyright (C) 2006--2009 William Stein and Jon Hanke
#
#  Distributed under the terms of the GNU General Public License (GPL)
#
#    This code is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    General Public License for more details.
#
#  The full text of the GPL is available at:
#
#                  http://www.gnu.org/licenses/
#*****************************************************************************

from sage.libs.pari.all import pari
from sage.rings.all import (is_fundamental_discriminant, ZZ, divisors, gcd)
from sage.structure.sage_object import SageObject
from sage.matrix.matrix_space import MatrixSpace_generic
from sage.matrix.constructor import Matrix
from sage.misc.cachefunc import cached_method
from sage.rings.arith import is_square, integer_ceil, integer_floor

class BinaryQF(SageObject):
    """
    A binary quadratic form over `\ZZ`.

    INPUT:

    - `v` -- a list or tuple of 3 entries:  [a,b,c], or a quadratic homogeneous
      polynomial in two variables with integer coefficients


    OUTPUT:

    the binary quadratic form a*x^2 + b*x*y + c*y^2.

    EXAMPLES::

        sage: b = BinaryQF([1,2,3])
        sage: b.discriminant()
        -8
        sage: b1 = BinaryQF(1,2,3)
        sage: b1 == b
        True
        sage: R.<x, y> = ZZ[]
        sage: BinaryQF(x^2 + 2*x*y + 3*y^2) == b
        True
        sage: BinaryQF(1,0,1)
        x^2 + y^2
    """
    # Initializes the form with a 3-element list
    def __init__(self, a, b=None, c=None):
        r"""
        Creates the binary quadratic form `ax^2 + bxy + cy^2` from the
        triple [a,b,c] over `\ZZ` or from a polynomial.

        INPUT:

        - ``a`` -- 3-tuple of integers, or a quadratic homogeneous polynomial
          in two variables with integer coefficients; or
          ``a``,``b``,``c`` -- three integers

        EXAMPLES::

            sage: Q = BinaryQF([1,2,3]); Q
            x^2 + 2*x*y + 3*y^2
            sage: Q = BinaryQF([1,2])
            Traceback (most recent call last):
            ...
            TypeError: Binary quadratic form must be given by a list of three coefficients

            sage: R.<x, y> = ZZ[]
            sage: f = x^2 + 2*x*y + 3*y^2
            sage: BinaryQF(f)
            x^2 + 2*x*y + 3*y^2
            sage: BinaryQF(f + x)
            Traceback (most recent call last):
            ...
            TypeError: Binary quadratic form must be given by a quadratic homogeneous bivariate integer polynomial

        TESTS::

            sage: BinaryQF(0)
            0
        """
        if isinstance(a, (list, tuple)):
            if len(a) == 3:
                # Let the ZZ() cast catch type errors
                try:
                    self._a = ZZ(a[0])
                    self._b = ZZ(a[1])
                    self._c = ZZ(a[2])
                except ValueError:
                    raise TypeError, "Binary quadratic form must be given by a list of three integers"
            else:
                raise TypeError, "Binary quadratic form must be given by a list of three coefficients"
        elif a in ZZ:
            try:
                self._a = ZZ(a)
                self._b = ZZ(b)
                self._c = ZZ(c)
            except ValueError:
                raise TypeError, "Binary quadratic form must be given by three integers"
        else:
            f = a
            from sage.rings.polynomial.multi_polynomial_element import is_MPolynomial
            if f.is_zero():
                self._a, self._b, self._c = [ZZ(0), ZZ(0), ZZ(0)]
            elif (is_MPolynomial(f) and f.is_homogeneous() and f.base_ring() == ZZ
                    and f.degree() == 2 and f.parent().ngens() == 2):
                x, y = f.parent().gens()
                self._a, self._b, self._c = [f.monomial_coefficient(mon) for mon in [x**2, x*y, y**2]]
            else:
                raise TypeError, "Binary quadratic form must be given by a quadratic homogeneous bivariate integer polynomial"
        self._poly = None

    def _pari_init_(self):
        """
        Used to convert this quadratic form to Pari.

        EXAMPLES::

            sage: f = BinaryQF([2,3,4]); f
            2*x^2 + 3*x*y + 4*y^2
            sage: f._pari_init_()
            'Qfb(2,3,4)'
            sage: pari(f)
            Qfb(2, 3, 4)
            sage: type(pari(f))
            <type 'sage.libs.pari.gen.gen'>
            sage: gp(f)
            Qfb(2, 3, 4)
            sage: type(gp(f))
            <class 'sage.interfaces.gp.GpElement'>
        """
        return 'Qfb(%s,%s,%s)'%(self._a,self._b,self._c)

    def __mul__(self, right):
        """
        Implementation of a "right action", either by a 2x2 integer matrix
        or as Gauss composition of binary quadratic forms.  The result need
        not be reduced.

        EXAMPLES:

        We explicitly compute in the group of classes of positive
        definite binary quadratic forms of discriminant -23.

        ::

            sage: R = BinaryQF_reduced_representatives(-23, primitive_only=False); R
            [x^2 + x*y + 6*y^2, 2*x^2 - x*y + 3*y^2, 2*x^2 + x*y + 3*y^2]
            sage: R[0] * R[0]
            x^2 + x*y + 6*y^2
            sage: R[1] * R[1]
            4*x^2 + 3*x*y + 2*y^2
            sage: (R[1] * R[1]).reduced_form()
            2*x^2 + x*y + 3*y^2
            sage: (R[1] * R[1] * R[1]).reduced_form()
            x^2 + x*y + 6*y^2
            sage: q1=BinaryQF((1,1,4))
            sage: M = Matrix(ZZ,[[1,3],[0,1]]);
            sage: q1*M
            x^2 + 7*x*y + 16*y^2
            sage: q1.matrix_action_right(M)
            x^2 + 7*x*y + 16*y^2
            sage: N = Matrix(ZZ,[[1,0],[1,0]]);
            sage: q1*(M*N) == q1.matrix_action_right(M).matrix_action_right(N)
            True

        """
        # Either a "right" action by
        # ...or Gaussian composition
        if isinstance(right, BinaryQF):
            # There could be more elegant ways, but qfbcompraw isn't
            # wrapped yet in the PARI C library.  We may as well settle
            # for the below, until somebody simply implements composition
            # from scratch in Cython.
            v = list(pari('qfbcompraw(%s,%s)'%(self._pari_init_(),
                                            right._pari_init_())))
            return BinaryQF(v)
        # ...or a 2x2 matrix...
        if isinstance(right.parent(), MatrixSpace_generic):
            if not (right.is_square() and right.ncols() == 2):
                raise ValueError, "Must be a 2 x 2 matrix"
            else:
                aa = right[0,0]
                bb = right[0,1]
                cc = right[1,0]
                dd = right[1,1]
                A = self.polynomial()(aa, cc)
                C = self.polynomial()(bb, dd)
                B = self.polynomial()(aa+bb,cc+dd) - A - C
                qf = BinaryQF(A, B, C)
                return qf
        raise TypeError, "Right operand must be binary quadratic form or 2x2 matrix"

    def __getitem__(self, n):
        """
        Return the n-th component of this quadratic form.

        If this form is `a x^2 + b x y + c y^2`, the 0-th component is `a`,
        the 1-st component is `b`, and `2`-nd component is `c`.

        Indexing is like lists -- negative indices and slices are allowed.

        EXAMPLES::


            sage: Q = BinaryQF([2,3,4])
            sage: Q[0]
            2
            sage: Q[2]
            4
            sage: Q[:2]
            (2, 3)
            sage: tuple(Q)
            (2, 3, 4)
            sage: list(Q)
            [2, 3, 4]
        """
        return (self._a, self._b, self._c)[n]

    def __call__(self, *args):
        r"""
        Evaluate this quadratic form at a point.

        INPUT:

        - args -- x and y values, as a pair x, y or a list, tuple, or
          vector

        EXAMPLES::


            sage: Q = BinaryQF([2, 3, 4])
            sage: Q(1, 2)
            24

        TESTS::

            sage: Q = BinaryQF([2, 3, 4])
            sage: Q([1, 2])
            24
            sage: Q((1, 2))
            24
            sage: Q(vector([1, 2]))
            24
        """
        if len(args) == 1:
            args = args[0]
        x, y = args
        return (self._a * x + self._b * y) * x + self._c * y**2

    def __cmp__(self, right):
        """
        Returns True if self and right are identical: the same coefficients.

        EXAMPLES::


            sage: P = BinaryQF([2,2,3])
            sage: Q = BinaryQF([2,2,3])
            sage: R = BinaryQF([1,2,3])
            sage: P == Q # indirect doctest
            True
            sage: P == R # indirect doctest
            False

        TESTS::

            sage: P == P
            True
            sage: Q == P
            True
            sage: R == P
            False
            sage: P == 2
            False
        """
        if not isinstance(right, BinaryQF):
            return cmp(type(self), type(right))
        return cmp((self._a,self._b,self._c), (right._a,right._b,right._c))

    def __add__(self, Q):
        """
        Returns the component-wise sum of two forms.

        That is, given `a_1 x^2 + b_1 x y + c_1 y^2` and `a_2 x^2 + b_2 x y +
        c_2 y^2`, returns the form
        `(a_1 + a_2) x^2 + (b_1 + b_2) x y + (c_1 + c_2) y^2.`

        EXAMPLES::


            sage: P = BinaryQF([2,2,3]); P
            2*x^2 + 2*x*y + 3*y^2
            sage: Q = BinaryQF([-1,2,2]); Q
            -x^2 + 2*x*y + 2*y^2
            sage: P + Q
            x^2 + 4*x*y + 5*y^2
            sage: P + Q == BinaryQF([1,4,5]) # indirect doctest
            True

        TESTS::

            sage: Q + P == BinaryQF([1,4,5]) # indirect doctest
            True
        """
        return BinaryQF([self._a + Q._a, self._b + Q._b, self._c + Q._c])

    def __sub__(self, Q):
        """
        Returns the component-wise difference of two forms.

        That is, given `a_1 x^2 + b_1 x y + c_1 y^2` and `a_2 x^2 + b_2 x y +
        c_2 y^2`, returns the form
        `(a_1 - a_2) x^2 + (b_1 - b_2) x y + (c_1 - c_2) y^2.`

        EXAMPLES::


            sage: P = BinaryQF([2,2,3]); P
            2*x^2 + 2*x*y + 3*y^2
            sage: Q = BinaryQF([-1,2,2]); Q
            -x^2 + 2*x*y + 2*y^2
            sage: P - Q
            3*x^2 + y^2
            sage: P - Q == BinaryQF([3,0,1]) # indirect doctest
            True

        TESTS::

            sage: Q - P == BinaryQF([3,0,1]) # indirect doctest
            False
            sage: Q - P != BinaryQF([3,0,1]) # indirect doctest
            True
        """
        return BinaryQF([self._a - Q._a, self._b - Q._b, self._c - Q._c])

    def _repr_(self):
        """
        Display the quadratic form.

        EXAMPLES::


            sage: Q = BinaryQF([1,2,3]); Q # indirect doctest
            x^2 + 2*x*y + 3*y^2

            sage: Q = BinaryQF([-1,2,3]); Q
            -x^2 + 2*x*y + 3*y^2

            sage: Q = BinaryQF([0,0,0]); Q
            0
        """
        return repr(self.polynomial())

    def _latex_(self):
        """
        Return latex representation of this binary quadratic form.

        EXAMPLES::

            sage: f = BinaryQF((778,1115,400)); f
            778*x^2 + 1115*x*y + 400*y^2
            sage: latex(f) # indirect doctest
            778 x^{2} + 1115 x y + 400 y^{2}
        """
        return self.polynomial()._latex_()

    def content(self):
        """
        Return the content of the form, i.e., the gcd of the coefficients.
        EXAMPLES:
        sage: Q=BinaryQF(22,14,10)
        sage: Q.content()
         2
        sage: Q=BinaryQF(4,4,-15)
        sage: Q.content()
         1
        """
        return gcd([self._a,self._b,self._c])

    @cached_method
    def polynomial(self):
        """
        Returns the binary quadratic form as a homogeneous 2-variable
        polynomial.

        EXAMPLES::

            sage: Q = BinaryQF([1,2,3])
            sage: Q.polynomial()
            x^2 + 2*x*y + 3*y^2

            sage: Q = BinaryQF([-1,-2,3])
            sage: Q.polynomial()
            -x^2 - 2*x*y + 3*y^2

            sage: Q = BinaryQF([0,0,0])
            sage: Q.polynomial()
             0

            Note: Cacheing in _poly seems to give a very slight
            improvement (~0.2 usec) in 'timeit()' runs.  Not sure it
            is worth the instance variable.
        """
        if self._poly == None:
            self._poly = self(ZZ['x, y'].gens())
        return self._poly

    @cached_method
    def discriminant(self):
        """
        Returns the discriminant `b^2 - 4ac` of this binary
        form (`ax^2 + bxy + cy^2`).

        EXAMPLES::


            sage: Q = BinaryQF([1,2,3])
            sage: Q.discriminant()
            -8
        """
        return self._b**2 - 4 * self._a * self._c

    def determinant(self):
        """
        The determinant of the matrix associated to this quadratic form.
        The determinant is used by Gauss and by Conway-Sloane (for whom
        an integral quadratic form has coefficients (a,2b,c) with a,b,c
        integers).

        OUTPUT:
            The determinant of the matrix [a,b/2;b/2,c] as a rational

        REMARK:
            This is just -D/4 where D is the discriminant.  The return
            type is rational even if b (and hence D) is even.

        EXAMPLE:
        sage: q = BinaryQF(1,-1,67)
        sage: q.determinant()
        267/4
        """
        return self._a*self._c-(self._b**2)/4

    @cached_method
    def has_fundamental_discriminant(self):
        """
        Checks if the discriminant D of this form is a fundamental
        discriminant (i.e. D is the smallest element of its
        squareclass with D = 0 or 1 mod 4).

        EXAMPLES::

            sage: Q = BinaryQF([1,0,1])
            sage: Q.discriminant()
            -4
            sage: Q.has_fundamental_discriminant()
            True

            sage: Q = BinaryQF([2,0,2])
            sage: Q.discriminant()
            -16
            sage: Q.has_fundamental_discriminant()
            False
        """
        return is_fundamental_discriminant(self.discriminant())

    @cached_method
    def is_primitive(self):
        """
        Checks if the form `ax^2 + bxy + cy^2`  satisfies
        `\gcd(a,b,c)=1`, i.e., is primitive.

        EXAMPLES::


            sage: Q = BinaryQF([6,3,9])
            sage: Q.is_primitive()
            False

            sage: Q = BinaryQF([1,1,1])
            sage: Q.is_primitive()
            True

            sage: Q = BinaryQF([2,2,2])
            sage: Q.is_primitive()
            False

            sage: rqf = BinaryQF_reduced_representatives(-23*9, primitive_only=False)
            sage: [qf.is_primitive() for qf in rqf]
            [True, True, True, False, True, True, False, False, True]
            sage: rqf
            [x^2 + x*y + 52*y^2,
            2*x^2 - x*y + 26*y^2,
            2*x^2 + x*y + 26*y^2,
            3*x^2 + 3*x*y + 18*y^2,
            4*x^2 - x*y + 13*y^2,
            4*x^2 + x*y + 13*y^2,
            6*x^2 - 3*x*y + 9*y^2,
            6*x^2 + 3*x*y + 9*y^2,
            8*x^2 + 7*x*y + 8*y^2]
            sage: [qf for qf in rqf if qf.is_primitive()]
            [x^2 + x*y + 52*y^2,
            2*x^2 - x*y + 26*y^2,
            2*x^2 + x*y + 26*y^2,
            4*x^2 - x*y + 13*y^2,
            4*x^2 + x*y + 13*y^2,
            8*x^2 + 7*x*y + 8*y^2]
        """
        return gcd([self._a, self._b, self._c])==1

    @cached_method
    def is_zero(self):
        """
        Report whether this quadratic form is identically zero.

        OUTPUT:
            True if the form is zero, else False.

        EXAMPLES:
            sage: Q=BinaryQF(195751,37615,1807)
            sage: Q.is_zero()
            False
            sage: Q=BinaryQF(0,0,0)
            sage: Q.is_zero()
            True
        """
        return self.content() == 0

    @cached_method
    def is_weakly_reduced(self):
        """
        Checks if the form `ax^2 + bxy + cy^2`  satisfies
        `|b| \leq a \leq c`, i.e., is weakly reduced.

        EXAMPLES::


            sage: Q = BinaryQF([1,2,3])
            sage: Q.is_weakly_reduced()
            False

            sage: Q = BinaryQF([2,1,3])
            sage: Q.is_weakly_reduced()
            True

            sage: Q = BinaryQF([1,-1,1])
            sage: Q.is_weakly_reduced()
            True
        """
        if self.discriminant() >= 0:
            raise NotImplementedError, "only implemented for negative discriminants"
        return (abs(self._b) <= self._a) and (self._a <= self._c)

    def _reduce_indef(self, DoMatrix=False):
        """
        Reduce an indefinite, non-reduced form.  If 'Matrix' is true,
        return both the reduced form and the matrix which produces the
        latter from the input (right-action).
        """
        from sage.functions.generalized import sign
        if DoMatrix:
            U = Matrix(ZZ,2,2,[1,0,0,1])
        d = self.discriminant().sqrt(prec=53)
        Q = self
        while not Q.is_reduced():
            a = Q._a
            b = Q._b
            c = Q._c
            cabs = c.abs()
            if cabs >= d:
                s = sign(c)*integer_floor(((cabs+b)/(2*cabs)))
            else:
                s = sign(c)*integer_floor(((d+b)/(2*cabs)))
            if DoMatrix:
                T = Matrix(ZZ,2,2,[0,-1,1,s])
                U=U*T
            Q = BinaryQF(c, -b+2*s*c, c*s*s-b*s+a)
#            print "(%s,%s,%s) -> %s"%(Q._a,Q._b,Q._c,Q.is_reduced())
        if DoMatrix:
            return Q, U
        return Q

    @cached_method
    def reduced_form(self, DoMatrix=False):
        """
        Return the unique reduced form equivalent to ``self``. See also
        :meth:`~is_reduced`.
        Returns a reduced form equivalent to the input form.  If 'Matrix'
        is True, also return the matrix creating the equivalent form.

        EXAMPLES::

            sage: a = BinaryQF([33,11,5])
            sage: a.is_reduced()
            False
            sage: b = a.reduced_form(); b
            5*x^2 - x*y + 27*y^2
            sage: b.is_reduced()
            True

            sage: a = BinaryQF([15,0,15])
            sage: a.is_reduced()
            True
            sage: b = a.reduced_form(); b
            15*x^2 + 15*y^2
            sage: b.is_reduced()
            True
        """
        if self.is_reduced():
            if DoMatrix:
                return self,Matrix(ZZ,2,2,[1,0,0,1])
            else:
                return self
        if self.discriminant() > 0:
            return self._reduce_indef(DoMatrix)

        v = list(pari('Vec(qfbred(Qfb(%s,%s,%s)))'%(self._a,self._b,self._c)))
        return BinaryQF(v)

    # Buchmann/Vollmer Cycle algorithm
    def _RhoTau(self, Proper):
        """
        Apply Rho and Tau operators to this form, returning
        a new form Q.
        """
        d = self.discriminant().sqrt(prec=53)
        a = self._a
        b = self._b
        c = self._c
        cabs = c.abs()
        sign = 1
        if c < 0: sign = -1
        if cabs >= d:
            s = sign*((cabs+b)/(2*cabs)).floor()
        else:
            s = sign*((d+b)/(2*cabs)).floor()
        Q=BinaryQF(-c,-b+2*s*c,-(a-b*s+c*s*s))
        return Q

    def Cycle(self, Proper=False):
        """
        Produce the cycle of reduced forms to which this (reduced, indefinite)
        form belongs.  This is used to test for equivalence between indefinite
        forms.  The cycle of a form consists of all equivalent forms with
        coefficient a>0.  The "proper" cycle consists of all equivalent forms,
        and is either the same as, or twice the size of, the cycle.  In the
        latter case, the cycle has odd length.

        EXAMPLES:
            sage: Q=BinaryQF(14,17,-2)
            sage: Q.Cycle()
            [14*x^2 + 17*x*y - 2*y^2, 2*x^2 + 19*x*y - 5*y^2, 5*x^2 + 11*x*y - 14*y^2]

            sage: Q=BinaryQF(1,8,-3)
            sage: Q.Cycle()
            [x^2 + 8*x*y - 3*y^2,
            3*x^2 + 4*x*y - 5*y^2,
            5*x^2 + 6*x*y - 2*y^2,
            2*x^2 + 6*x*y - 5*y^2,
            5*x^2 + 4*x*y - 3*y^2,
            3*x^2 + 8*x*y - y^2]

            sage: Q=BinaryQF(1,7,-6)
            sage: Q.Cycle()
            [x^2 + 7*x*y - 6*y^2,
            6*x^2 + 5*x*y - 2*y^2,
            2*x^2 + 7*x*y - 3*y^2,
            3*x^2 + 5*x*y - 4*y^2,
            4*x^2 + 3*x*y - 4*y^2,
            4*x^2 + 5*x*y - 3*y^2,
            3*x^2 + 7*x*y - 2*y^2,
            2*x^2 + 5*x*y - 6*y^2,
            6*x^2 + 7*x*y - y^2]
        """
        if not (self.is_indef() and self.is_reduced()):
            raise ValueError, "%s must be indefinite and reduced"%self
        C = [self]
        Q1 = self._RhoTau(Proper)
        while not self == Q1:
            C.append(Q1)
            Q1 = Q1._RhoTau(Proper)
        self._cycle_list = C
        return C

    def is_posdef(self):
        """
        Report whether the form is positive definite.

        OUTPUT:
            True if this form is positive definite, i.e., has a
            negative discriminant with self._a > 0.
        EXAMPLES:
            sage: Q=BinaryQF(195751,37615,1807)
            sage: Q.is_posdef()
            True
            sage: Q=BinaryQF(195751,1212121,-1876411)
            sage: Q.is_posdef()
            False
        """
        return self.discriminant() < 0 and self._a > 0

    def is_negdef(self):
        """
        Report whether the form is negative definite.

        OUTPUT:
            True if this form is negative definite, i.e., has a
            negative discriminant with self._a < 0.

        EXAMPLES:
            sage: Q=BinaryQF(-1,3,-5)
            sage: Q.is_posdef()
            False
            sage: Q.is_negdef()
            True
        """
        return self.discriminant() < 0 and self._a < 0

    def is_indef(self):
        """
        Report whether the form is indefinite.

        OUTPUT:
            True if this form is indefinite, i.e., has discriminant > 0.

        EXAMPLES:
            sage: Q=BinaryQF(1,3,-5)
            sage: Q.is_indef()
            True
        """
        return self.discriminant() > 0

    def is_singular(self):
        """
        Report whether the form is singular.

        OUTPUT:
            True if this form is singular, i.e., has zero discriminant.

        EXAMPLES:
            sage: Q=BinaryQF(1,3,-5)
            sage: Q.is_singular()
            False
            sage: Q=BinaryQF(1,2,1)
            sage: Q.is_singular()
            True
        """
        return self.discriminant().is_zero()

    def is_nonsingular(self):
        """
        Report whether the form is nonsingular.

        OUTPUT:
            True if this form is nonsingular, i.e., has non-zero discriminant.

        EXAMPLES:
            sage: Q=BinaryQF(1,3,-5)
            sage: Q.is_nonsingular()
            True
            sage: Q=BinaryQF(1,2,1)
            sage: Q.is_nonsingular()
            False
        """
        return not self.discriminant().is_zero()

    def is_equivalent(self, right):
        """
        Returns whether self is properly equivalent to Q.

        INPUT::
        - ``right`` -- a binary quadratic form

        EXAMPLES::
            sage: Q3 = BinaryQF(4,4,15)
            sage: Q2 = BinaryQF(4,-4,15)
            sage: Q2.is_equivalent(Q3)
            True
            sage: a = BinaryQF([33,11,5])
            sage: b = a.reduced_form(); b
            5*x^2 - x*y + 27*y^2
            sage: a.is_equivalent(b)
            True
            sage: a.is_equivalent(BinaryQF((3,4,5)))
            False
        """
        if type(right) != type(self):
            raise ValueError, "\'%s\' is not a BinaryQF."%right
        if self.discriminant() != right.discriminant():
            return False
        if self.is_indef():
            # First, reduce self and get a positive lead coefficient
            # Check if already reduced to avoid going through another
            #  reduction (which can happen for indefinite forms).
            if self.is_reduced():
                RedSelf = self
            else:
                RedSelf = self.reduced_form()
            if RedSelf._a < 0:
                RedSelf = BinaryQF(-RedSelf._a, RedSelf._b, -RedSelf._c)
            _ = right.Cycle()                  # This caches the list
            return RedSelf in right._cycle_list
        # Else we're dealing with definite forms.
        if self.is_posdef() and not right.is_posdef():
            return False
        if self.is_negdef() and not right.is_negdef():
            return False
        Q1 = self.reduced_form()
        Q2 = right.reduced_form()
        return Q1 == Q2

    @cached_method
    def is_reduced(self):
        """
        Checks if the quadratic form is reduced, i.e., if the form
        `ax^2 + bxy + cy^2` satisfies `|b|\leq a \leq c`, and
        that `b\geq 0` if either `a = b` or `a = c`.

        EXAMPLES::

            sage: Q = BinaryQF([1,2,3])
            sage: Q.is_reduced()
            False

            sage: Q = BinaryQF([2,1,3])
            sage: Q.is_reduced()
            True

            sage: Q = BinaryQF([1,-1,1])
            sage: Q.is_reduced()
            False

            sage: Q = BinaryQF([1,1,1])
            sage: Q.is_reduced()
            True
        """
        if self.discriminant() < 0:
            return (-self._a < self._b <= self._a < self._c) or \
                (ZZ(0) <= self._b <= self._a == self._c)
        else:
            d = self.discriminant().sqrt(prec=53)
            return (d-2*self._a.abs()).abs() < self._b < d

    def complex_point(self):
        r"""
        Returns the point in the complex upper half-plane associated
        to this (positive definite) quadratic form.

        For positive definite forms with negative discriminants, this is a
        root `\tau` of `a x^2 + b x + c` with the imaginary part of `\tau`
        greater than 0.

        EXAMPLES::

            sage: Q = BinaryQF([1,0,1])
            sage: Q.complex_point()
            1.00000000000000*I
        """
        if self.discriminant() >= 0:
            raise NotImplementedError, "only implemented for negative discriminant"
        R = ZZ['x']
        x = R.gen()
        Q1 = R(self.polynomial()(x,1))
        return [z  for z in Q1.complex_roots()  if z.imag() > 0][0]

    def matrix_action_left(self, M):
        r"""
        Return the binary quadratic form resulting from the left action
        of the 2-by-2 matrix ``M`` on the quadratic form ``self``.

        Here the action of the matrix `M = \begin{pmatrix} a & b \\ c & d
        \end{pmatrix}` on the form `Q(x, y)` produces the form `Q(ax+by,
        cx+dy)`.

        EXAMPLES::

            sage: Q = BinaryQF([2, 1, 3]); Q
            2*x^2 + x*y + 3*y^2
            sage: M = matrix(ZZ, [[1, 2], [3, 5]])
            sage: Q.matrix_action_left(M)
            16*x^2 + 83*x*y + 108*y^2
        """
        v, w = M.rows()
        a1 = self(v)
        c1 = self(w)
        b1 = self(v + w) - a1 - c1
        return BinaryQF([a1, b1, c1])

    def matrix_action_right(self, M):
        r"""
        Return the binary quadratic form resulting from the right action
        of the 2-by-2 matrix ``M`` on the quadratic form ``self``.

        Here the action of the matrix `M = \begin{pmatrix} a & b \\ c & d
        \end{pmatrix}` on the form `Q(x, y)` produces the form `Q(ax+cy,
        bx+dy)`.

        EXAMPLES::

            sage: Q = BinaryQF([2, 1, 3]); Q
            2*x^2 + x*y + 3*y^2
            sage: M = matrix(ZZ, [[1, 2], [3, 5]])
            sage: Q.matrix_action_right(M)
            32*x^2 + 109*x*y + 93*y^2
        """
        v, w = M.columns()
        a1 = self(v)
        c1 = self(w)
        b1 = self(v + w) - a1 - c1
        return BinaryQF([a1, b1, c1])

def BinaryQF_reduced_representatives(D, primitive_only=True):
    r"""
    Compute representatives of the classes of (positive definite or
    indefinite) binary quadratic forms of discriminant D.


    INPUT:

    - ``D`` -- (integer) A discriminant.

    - ``primitive_only`` -- (bool, default False) flag controlling whether only
      primitive forms are included.

    OUTPUT:

    (list) A lexicographically-ordered list of inequivalent reduced
    representatives for the equivalence classes of binary quadratic
    forms of discriminant `D`.  If ``primitive_only`` is ``True`` then
    imprimitive forms (which only exist when `D` is not fundamental) are
    omitted; otherwise they are included.

    EXAMPLES::

        sage: BinaryQF_reduced_representatives(-4, primitive_only=False)
        [x^2 + y^2]

        sage: BinaryQF_reduced_representatives(-163, primitive_only=False)
        [x^2 + x*y + 41*y^2]

        sage: BinaryQF_reduced_representatives(-12, primitive_only=False)
        [x^2 + 3*y^2, 2*x^2 + 2*x*y + 2*y^2]

        sage: BinaryQF_reduced_representatives(-16, primitive_only=False)
        [x^2 + 4*y^2, 2*x^2 + 2*y^2]

        sage: BinaryQF_reduced_representatives(-63, primitive_only=False)
        [x^2 + x*y + 16*y^2, 2*x^2 - x*y + 8*y^2, 2*x^2 + x*y + 8*y^2, 3*x^2 + 3*x*y + 6*y^2, 4*x^2 + x*y + 4*y^2]

    The number of inequivalent reduced binary forms with a fixed negative
    fundamental discriminant D is the class number of the quadratic field
    `Q(\sqrt{D})`::

        sage: len(BinaryQF_reduced_representatives(-13*4, primitive_only=False))
        2
        sage: QuadraticField(-13*4, 'a').class_number()
        2
        sage: p=next_prime(2^20); p
        1048583
        sage: len(BinaryQF_reduced_representatives(-p, primitive_only=False))
        689
        sage: QuadraticField(-p, 'a').class_number()
        689

        sage: BinaryQF_reduced_representatives(-23*9, primitive_only=False)
        [x^2 + x*y + 52*y^2,
        2*x^2 - x*y + 26*y^2,
        2*x^2 + x*y + 26*y^2,
        3*x^2 + 3*x*y + 18*y^2,
        4*x^2 - x*y + 13*y^2,
        4*x^2 + x*y + 13*y^2,
        6*x^2 - 3*x*y + 9*y^2,
        6*x^2 + 3*x*y + 9*y^2,
        8*x^2 + 7*x*y + 8*y^2]
        sage: BinaryQF_reduced_representatives(-23*9)
        [x^2 + x*y + 52*y^2,
        2*x^2 - x*y + 26*y^2,
        2*x^2 + x*y + 26*y^2,
        4*x^2 - x*y + 13*y^2,
        4*x^2 + x*y + 13*y^2,
        8*x^2 + 7*x*y + 8*y^2]

    TESTS::

        sage: BinaryQF_reduced_representatives(73, primitive_only=False)
        [-6*x^2 + 5*x*y + 2*y^2, -6*x^2 + 7*x*y + y^2, -4*x^2 + 3*x*y + 4*y^2, -4*x^2 + 5*x*y + 3*y^2, -3*x^2 + 5*x*y + 4*y^2, -3*x^2 + 7*x*y + 2*y^2, -2*x^2 + 5*x*y + 6*y^2, -2*x^2 + 7*x*y + 3*y^2, -x^2 + 7*x*y + 6*y^2, x^2 + 7*x*y - 6*y^2, 2*x^2 + 5*x*y - 6*y^2, 2*x^2 + 7*x*y - 3*y^2, 3*x^2 + 5*x*y - 4*y^2, 3*x^2 + 7*x*y - 2*y^2, 4*x^2 + 3*x*y - 4*y^2, 4*x^2 + 5*x*y - 3*y^2, 6*x^2 + 5*x*y - 2*y^2, 6*x^2 + 7*x*y - y^2]
        sage: BinaryQF_reduced_representatives(76)
        [-5*x^2 + 4*x*y + 3*y^2, -5*x^2 + 6*x*y + 2*y^2, -3*x^2 + 4*x*y + 5*y^2, -3*x^2 + 8*x*y + y^2, -2*x^2 + 6*x*y + 5*y^2, -x^2 + 8*x*y + 3*y^2, x^2 + 8*x*y - 3*y^2, 2*x^2 + 6*x*y - 5*y^2, 3*x^2 + 4*x*y - 5*y^2, 3*x^2 + 8*x*y - y^2, 5*x^2 + 4*x*y - 3*y^2, 5*x^2 + 6*x*y - 2*y^2]
    """
    from sage.sets.set import Set
    if D not in ZZ:
        print "%s not an Integer"%(D,)
        return []
    if is_square(D):
        print "%s is a square.  Tsk tsk"%D
        return []
    D = ZZ(D)

    # For a fundamental discriminant all forms are primitive so we need not check:
    if primitive_only:
        primitive_only = not is_fundamental_discriminant(D)

    form_list = []

    from sage.misc.all import xsrange

    # Only iterate over positive a and over b of the same
    # parity as D such that 4a^2 + D <= b^2 <= a^2
    D4 = D%4
    if D4 == 2 or D4 == 3:
        raise ValueError, "%s is not a discriminant."%D
    if D > 0:           # Indefinite
        sqrt_d = D.sqrt(prec=53)
        for b in xsrange(1, int(sqrt_d)+1):
            if (D-b)%2 != 0:
                continue
            A = (D-b**2)/4
            Low_a = int(integer_ceil((sqrt_d-b)/2))
            High_a = int(integer_ceil((sqrt_d+b)/2))
            for a in xsrange(Low_a, High_a):
                if a == 0:
                    continue
                c = -A/a
                if c in ZZ:
                    Q=BinaryQF(a,b,c)
                    Q1=BinaryQF(-a,b,-c)
                    form_list.append(Q)
                    form_list.append(Q1)
    else:               # Definite
        for a in xsrange(1,1+((-D)//3).isqrt()):
            a4 = 4*a
            s = D + a*a4
            w = 1+(s-1).isqrt() if s > 0 else 0
            if w%2 != D%2: w += 1
            for b in xsrange(w,a+1,2):
                t = b*b-D
                if t % a4 == 0:
                    c = t // a4
                    if (not primitive_only) or gcd([a,b,c])==1:
                        if b>0 and a>b and c>a:
                            form_list.append(BinaryQF([a,-b,c]))
                        form_list.append(BinaryQF([a,b,c]))

    form_list.sort()
    return form_list
