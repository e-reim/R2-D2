from time import time, clock, sleep
import os
import subprocess

FASTER_COMPUTER = 1
SLOW_COMPUTER = 3
VERY_SLOW_COMPUTER = 5


class IronbotException(Exception):
    pass

class UserError(Exception):
    def __init__(self, exc, txt):
        Exception.__init__(self,u'%s (%s)' % (txt, unicode(exc)))

def get_function(seq):
    i = iter(seq)
    def fun():
        return i.next()
    return fun

def error_decorator(f):
    """
    >>> @error_decorator
    ... def f(a):
    ...     "abc"
    ...     if a: return 0
    ...     raise Exception("An utter failure happened")
    >>> f.__doc__
    'abc'
    >>> f(1)
    0
    >>> try:
    ...     f(0)
    ... except Exception, e:
    ...     print str(e)
    An utter failure happened
    >>> try:
    ...     f(0, failure_text="YES!")
    ... except Exception, e:
    ...     print str(e)
    YES! (An utter failure happened)
    """
    def wrapper(*a, **kw):
        failure_text = kw.get('failure_text', None)
        if 'failure_text' in kw:
            del kw['failure_text']
        try:
            return f(*a, **kw)
        except Exception, e:
            if failure_text is None:
                raise
            raise UserError(e, failure_text)
    wrapper.__doc__ = f.__doc__
    return wrapper


def assert_raises(exc, f, *a, **kw):
    """
    >>> def raiser(*a, **kw):
    ...     print a, kw
    ...     raise IndexError("")
    >>> def no_raiser(*a, **kw):
    ...     print a, kw
    ...
    >>> assert_raises(Exception, raiser, 1, 2, q=0)
    (1, 2) {'q': 0}
    >>> res = False
    >>> try: assert_raises(Exception, no_raiser, 1, 2, q=0)
    ... except AssertionError: res = True
    (1, 2) {'q': 0}
    >>> assert res
    """
    try:
        f(*a, **kw)
    except exc:
        return
    raise AssertionError("A function has not raised the exception you are waiting for")

def timing():
    print("timing")
    begin_time = time()
    p = subprocess.call('ipy test.py', shell=True)
    sum_time = time() - begin_time
    return sum_time

class Delay(object):
    COEFF = (('ms', 0.001), ('s', 1.0), ('m', 60.0), ('h', 3600.0)) #The order is significant!!!
    FOREVER = 'forever'
    BENCHMARKED_FLAG = '~'
    BENCHMARK_INITIAL = False
    if not BENCHMARK_INITIAL:
       BENCHMARK = 2     #Lower is better (faster computer)
    @classmethod
    def do_benchmarking(cls, time_f=time):
        """
        >>> Delay.BENCHMARK=None
        >>> Delay.do_benchmarking(get_function((0, FASTER_COMPUTER*0.5)))
        >>> Delay.BENCHMARK
        1
        >>> Delay.BENCHMARK=None
        >>> Delay.do_benchmarking(get_function((FASTER_COMPUTER,SLOW_COMPUTER)))
        >>> Delay.BENCHMARK
        3
        >>> Delay.BENCHMARK=None
        >>> Delay.do_benchmarking(get_function((0,FASTER_COMPUTER*5)))
        >>> Delay.BENCHMARK
        5
        >>> Delay.BENCHMARK=7
        >>> Delay.do_benchmarking(get_function((0,FASTER_COMPUTER*5)))
        >>> Delay.BENCHMARK
        7
        >>> Delay.BENCHMARK=None
        >>> Delay.do_benchmarking(get_function((0,FASTER_COMPUTER*1.5)))
        >>> Delay.BENCHMARK
        3
        >>> Delay.BENCHMARK=None
        >>> Delay.do_benchmarking(get_function((0,0)))
        >>> Delay.BENCHMARK
        1
    """
        if cls.BENCHMARK is None:
            cls.BENCHMARK_INITIAL = True
            cls.BENCHMARK = FASTER_COMPUTER
            begin_time = time_f()
            p = subprocess.call('ipy test.py', shell=True)
            s_time = time_f() - begin_time
            if s_time > 1 and s_time < 4:
               cls.BENCHMARK = SLOW_COMPUTER
            if s_time > 4:
              cls.BENCHMARK = VERY_SLOW_COMPUTER

    def __cmp__(self, sec):
        """
        >>> Delay('forever') == Delay('forever'), Delay('forever') > Delay('10s'), Delay('10s') < Delay('forever')
        (True, True, True)
        >>> Delay('10s') == Delay('10s'), Delay('11s') > Delay('10s'), Delay('10s') < Delay('11s')
        (True, True, True)
        >>> Delay('forever') == None, Delay('forever') > 10, 10 < Delay('forever')
        (True, True, True)
        >>> Delay('10s') == 10, Delay('11s') > 10, Delay('10s') < 11
        (True, True, True)
        >>> 11 > Delay('10s'), 9 < Delay('10s'), 10 == Delay('10s')
        (True, True, True)
        """
        if isinstance(sec, Delay):
            sec = sec.value
        if sec is None:
            if self.value is None:
                return 0
            return -1
        if self.value is None or self.value > sec:
            return 1
        if self.value < sec:
            return -1
        return 0


    def __init__(self, s):
        """
        >>> from math import fabs
        >>> assert fabs(Delay(' 10s ').value - 10) < 0.00001
        >>> assert fabs(Delay('10ms').value - 0.01) < 0.00001
        >>> assert_raises(IronbotException, Delay, '10ns')
        >>> assert_raises(IronbotException, Delay, 'a10s')
        >>> assert fabs(Delay(' ~10s ').value - 20) < 0.00001
        >>> assert fabs(Delay('~10ms').value - 0.02) < 0.00001
        >>> assert_raises(IronbotException, Delay, '~10ns')
        >>> assert_raises(IronbotException, Delay, '~a10s')
        >>> assert Delay('forever').value is None
        """
        s = s.strip()
        if s.lower() == self.FOREVER:
            self.value = None
            return
        k = None
        for u, v in self.COEFF:
            if s.endswith(u):
                k = v
                s = s[:-len(u)]
                break
        if not k:
            raise IronbotException("Cannot parse a delay value, no time units given: '%s'" % s)

        if s.startswith(self.BENCHMARKED_FLAG):
            s = s[len(self.BENCHMARKED_FLAG):]
            k *= self.BENCHMARK

        try:
            self.value = float(s) * k
        except ValueError:
            raise IronbotException("Cannot parse a delay value, it should contain a float value: '%s'" % s)


TIME_ACCURACY = 0.0001
WAIT_GRANULARITY = 0.2

def waiting_iterator(timeout):
    t0 = clock()
    first_loop = True
    while first_loop or (timeout and timeout >= clock() - t0 - TIME_ACCURACY):
        first_loop = False
        yield
        if timeout and timeout.value:
            sleep(WAIT_GRANULARITY)
    if timeout and timeout.value:
        yield

def _negate(not_found, v):
    if not_found:
        return not bool(v)
    return bool(v)

def result_modifier(res, src_list=None, not_found=False, any=False, all=False, single=False, none=False, number=None,
                    prefer_bool=False, index=None):
    """
    >>> result_modifier([], not_found=True, any=True)
    (False, [], "The result does not match 'any' flag")
    >>> result_modifier([], any=True)
    (False, [], "The result does not match 'any' flag")
    >>> result_modifier([], not_found=True, all=True)
    (True, [], None)
    >>> result_modifier([], all=True)
    (True, [], None)
    >>> result_modifier([], not_found=True, single=True)
    (False, [], "The result does not match 'single' flag, found 0 item(s)")
    >>> result_modifier([], single=True)
    (False, [], "The result does not match 'single' flag, found 0 item(s)")
    >>> result_modifier([], not_found=True, none=True)
    (True, True, None)
    >>> result_modifier([], none=True)
    (True, True, None)
    >>> result_modifier([], not_found=True, number=0)
    (True, [], None)
    >>> result_modifier([], number=0)
    (True, [], None)
    >>> result_modifier([], number=1)
    (False, [], "The result does not match 'number' value, found 0 item(s)")
    >>> result_modifier([], number=1)
    (False, [], "The result does not match 'number' value, found 0 item(s)")
    >>> result_modifier([None], not_found=True, any=True)
    (True, [None], None)
    >>> result_modifier([None], any=True)
    (False, [None], "The result does not match 'any' flag")
    >>> result_modifier([None], not_found=True, all=True)
    (True, [None], None)
    >>> result_modifier([None], all=True)
    (False, [None], "The result does not match 'all' flag")
    >>> result_modifier([None], not_found=True, single=True)
    (True, None, None)
    >>> result_modifier([None], single=True)
    (False, [None], "The result does not match 'single' flag, found 0 item(s)")
    >>> result_modifier([None], not_found=True, none=True)
    (False, False, "The result does not match 'none' flag, found 1 item(s)")
    >>> result_modifier([None], none=True)
    (True, True, None)
    >>> result_modifier([None], not_found=True, number=0)
    (False, [None], "The result does not match 'number' value, found 1 item(s)")
    >>> result_modifier([None], number=0)
    (True, [None], None)
    >>> result_modifier([None], not_found=True, number=1)
    (True, [None], None)
    >>> result_modifier([None], number=1)
    (False, [None], "The result does not match 'number' value, found 0 item(s)")
    >>> result_modifier([1], not_found=True, any=True)
    (False, [1], "The result does not match 'any' flag")
    >>> result_modifier([1], not_found=True, any=True, prefer_bool=True)
    (False, False, "The result does not match 'any' flag")
    >>> result_modifier([1], any=True)
    (True, [1], None)
    >>> result_modifier([1], not_found=True, all=True)
    (False, [1], "The result does not match 'all' flag")
    >>> result_modifier([1], all=True)
    (True, [1], None)
    >>> result_modifier([1], not_found=True, single=True)
    (False, [1], "The result does not match 'single' flag, found 0 item(s)")
    >>> result_modifier([1], single=True)
    (True, 1, None)
    >>> result_modifier([1], not_found=True, none=True)
    (True, True, None)
    >>> result_modifier([1], none=True)
    (False, False, "The result does not match 'none' flag, found 1 item(s)")
    >>> result_modifier([1], not_found=True, number=0)
    (True, [1], None)
    >>> result_modifier([1], number=0)
    (False, [1], "The result does not match 'number' value, found 1 item(s)")
    >>> result_modifier([1], not_found=True, number=1)
    (False, [1], "The result does not match 'number' value, found 0 item(s)")
    >>> result_modifier([1], number=1)
    (True, [1], None)
    >>> v = False
    >>> try: result_modifier([], all=True, any=True)
    ... except IronbotException: v = True
    >>> assert v
    >>> result_modifier([], single=True, none=True)
    (True, None, None)
    >>> result_modifier([1], single=True, none=True)
    (True, 1, None)
    >>> result_modifier([1], src_list=1)
    (True, 1, None)
    >>> result_modifier([1], src_list=[1])
    (True, [1], None)
    >>> result_modifier([1], src_list=1, single=True)
    (True, 1, None)
    >>> result_modifier([1], src_list=1, index=0)
    (True, 1, None)
    """
    def make_prefer_bool(ok, res, msg):
        if prefer_bool:
            res = ok
        return ok, res, msg


    single_or_none = not (isinstance(src_list, list) or src_list is None)
    initial_none = none
    initial_single = single
    if not initial_none and not initial_single:
        initial_single = not isinstance(src_list, list)
    if single and none:
        single, none = False, False
        single_or_none = True

    if single_or_none and (single or none):
        single_or_none = False

    if len([v for v in (any, all, single, none, single_or_none, (number is not None)) if v]) > 1:
        raise IronbotException("Of the following only 'single' and 'none' may be combined: 'any', 'all', 'single', 'none', 'number'")

    if len([v for v in (any, all, single, none, (number is not None), (index is not None)) if v]) > 1:
        raise IronbotException("'index' is incompatible with 'single', 'none', 'any', 'all' and 'number'")

    filtered = [v for v in res if _negate(not_found, v)]
    if index is not None:
        if len(filtered) <= index:
            return make_prefer_bool(False, None, "Not enough items found for 'index' value")
        return make_prefer_bool(True, filtered[index], None)
    elif any:
        if len(filtered):
            return make_prefer_bool(True, res, None)
        return make_prefer_bool(False, res, "The result does not match 'any' flag")
    elif all:
        if len(filtered) == len(res):
            return make_prefer_bool(True, res, None)
        return make_prefer_bool(False, res, "The result does not match 'all' flag")
    elif none:
        if len(filtered) == 0:
            return make_prefer_bool(True, True, None)
        return make_prefer_bool(False, False, "The result does not match 'none' flag, found %d item(s)" % len(filtered))
    elif single:
        if len(filtered) == 1:
            return make_prefer_bool(True, res[0], None)
        return make_prefer_bool(False, res, "The result does not match 'single' flag, found %d item(s)" % len(filtered))
    elif number is not None:
        if len(filtered) == number:
            return make_prefer_bool(True, res, None)
        return make_prefer_bool(False, res, "The result does not match 'number' value, found %d item(s)" % len(filtered))
    elif single_or_none:
        if len(filtered) == 0:
            return make_prefer_bool(initial_none, None, None if initial_none else 'Expected none, got something')
        if len(filtered) == 1:
            return make_prefer_bool(initial_single, res[0], None if initial_single else 'Expected single result, got something')
        return make_prefer_bool(False, res, "The result does not match 'single' or 'none' value")
    return make_prefer_bool(True, res, None)
