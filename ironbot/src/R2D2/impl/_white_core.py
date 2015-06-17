import logging
import re

from _params import Delay, fixed_val, pop, pop_re, pop_type, robot_args, pop_bool
from _util import IronbotException, waiting_iterator, result_modifier
from _attr import AttributeDict
from _attr import attr_checker, re_checker, my_getattr, attr_reader

try:
    import clr
    clr.AddReference("White.Core")
    clr.AddReference("System")
    clr.AddReference("System.Core")
    clr.AddReference("UIAutomationClient")
    clr.AddReference("UIAutomationTypes")



    import White.Core.Application as Application
    from System.Diagnostics import ProcessStartInfo, Process
    import White.Core.Desktop as Desktop
    from System.Windows.Automation import AutomationProperty, AutomationElement

    from White.Core.UIItems.Finders import SearchCriteria

    from White.Core.UIItems import Button, TextBox, RadioButton, Label

    from White.Core.UIItems.ListBoxItems import ListBox, ListItem
    #import White.Core.UIItems
    #logging.warning(repr(dir(White.Core.UIItems)))
    #from White.Core.UIItems.TreeItems import Tree, TreeNode
    #from White.Core.UIItems.WindowItems import Window, DisplayState
    #from White.Core.UIItems.WindowStripControls import ToolStrip, MenuBar
    from White.Core.UIItems.MenuItems import Menu
    #from White.Core.UIItems.ListBoxItems import ComboBox
    #from White.Core.UIItems.TableItems import Table

    #from System.Windows.Automation import ControlType

    #logging.warning(repr(dir(ControlType)))


except:
    from traceback import format_exc
    logging.error(format_exc())


def full_text(parent):
    labels = [i for i in parent.GetMultiple(SearchCriteria.ByControlType(Label))]
    buttons = [i for i in parent.GetMultiple(SearchCriteria.ByControlType(Button))]
    return [i.Text for i in labels] + [i.Name for i in buttons]


FIND_WND_PARAMS = {
    'forever': (
        ('wait', fixed_val(Delay(Delay.FOREVER))),
    ),
    'wait': (
        ('wait', pop_type(Delay)),
    ),
    'app': {
        ('app', pop),
    }
}

KILL_PARAMS = {
}


WAIT_GRANULARITY = 0.2
TIME_ACCURACY = 0.0001

BOOL = {
    'True': True,
    'False': False
}

class IronbotTimeoutException(IronbotException):
    pass


TEST_CONTROLLED_APPS = [] #None
SUITE_CONTROLLED_APPS = [] #None


def ironbot_test_setup():
    global TEST_CONTROLLED_APPS
    TEST_CONTROLLED_APPS = []


def ironbot_test_teardown():
    global TEST_CONTROLLED_APPS
    ca = TEST_CONTROLLED_APPS
    TEST_CONTROLLED_APPS = []
    if ca is None:
        raise IronbotException("'Ironbot Test Teardown' keyword is used without 'Ironbot Test Setup'")
    for a in ca:
        if not a.HasExited:
            logging.warning('Test teardown: an app is still running')
            a.Dispose()


def ironbot_suite_setup():
    global SUITE_CONTROLLED_APPS
    SUITE_CONTROLLED_APPS = []


def ironbot_suite_teardown():
    global SUITE_CONTROLLED_APPS
    ca = SUITE_CONTROLLED_APPS
    SUITE_CONTROLLED_APPS = []
    if ca is None:
        raise IronbotException("'Ironbot Suite Teardown' keyword is used without 'Ironbot Suite Setup'")
    for a in ca:
        if not a.HasExited:
            logging.warning('Suite teardown: an app is still running')
            a.Dispose()

LAUNCH_PARAMS = (
    (pop,), {
       'suite_teardown': (('teardown', fixed_val('suite')),),
       'test_teardown': (('teardown', fixed_val('test')),),
       'assert': (('_assert', fixed_val(True)),),
       'params': (('params', pop),),
    }
)


def get_aid(obj):
    return obj.AutomationElement.GetCurrentPropertyValue(AutomationElement.AutomationIdProperty)


def check_aid(obj, v):
    return get_aid(obj) == v


def re_check_aid(obj, rexp):
    return rexp.match(get_aid(obj)) is not None


@robot_args(LAUNCH_PARAMS)
def app_launch(executable, teardown=None, params='', _assert=False):
    """
    Launches an app. The first parameter is a path to the app's executable. Optional 'suite_teardown' or 'test_teardown'
    flags force to kill the app at the end of the suite or of the test, respectively (if still running).
    A 'params' named parameter is also optional, should be followed by a parameters string (all args in one).
    """
    #logging.warning('EXEC ' + executable + ' ' + params)
    pi = ProcessStartInfo(executable, params)
    try:
        app = Application.Launch(pi)
    except:
        if _assert:
            logging.error('Failed to launch an executable')
            raise
        logging.warning('Failed to launch an executable')
        return None
    if teardown == 'test':
        TEST_CONTROLLED_APPS.append(app)
    elif teardown == 'suite':
        SUITE_CONTROLLED_APPS.append(app)

    return app


def proc_list():
    return [p for p in Process.GetProcesses()]


class _tchk(object):
    def __init__(self, a, v):
        setattr(self, a, v)


def _check_automation_id(cval):
    return lambda v: v.AutomationElement.GetCurrentPropertyValue(AutomationElement.AutomationIdProperty) == cval


def _re_check_automation_id(rexp):
    def _res(v):
        try:
            return rexp.match(v.AutomationElement.GetCurrentPropertyValue(AutomationElement.AutomationIdProperty)) is not None
        except:
            return False
    return _res


def do_filtering(li, *filters):
    """
    >>> do_filtering([1, 2])
    [1, 2]
    >>> do_filtering([1, 2], None)
    [1, 2]
    >>> do_filtering([1, 2], lambda x: x == 1)
    [1]
    >>> do_filtering([1, 2], lambda x: x == 1, lambda x: x == 2)
    []
    """
    for f in filters:
        if f:
            li = filter(f, li)
    return li


def _rechk(an):
    """
    >>> _rechk("q")("a.a")(_tchk("q", "aha")) and not _rechk("q")("a.a")(_tchk("q", "ahb"))
    True
    >>> _rechk("q")("a.adfas")(_tchk("q", "aha"))
    False
    """
    def _chk(reval):
        rexp = re.compile(reval)
        def _res(s):
            try:
                return rexp.match(my_getattr(s, an)) is not None
            except:
                return False
        return _res
    return _chk


PROC_ATTRS = AttributeDict()
PROC_ATTRS.add_attr('id', '', wait=(pop,), get=())
PROC_ATTRS.add_class_attr('Process', 'id', wait=attr_checker('Id'), get=attr_reader('Id'))
PROC_ATTRS.add_attr('title', '', wait=(pop,), get=())
PROC_ATTRS.add_class_attr('Process', 'title', wait=attr_checker('MainWindowTitle'), get=attr_reader('MainWindowTitle'))
PROC_ATTRS.add_attr('re_title', '', wait=(pop_re,))
PROC_ATTRS.add_class_attr('Process', 're_title', wait=re_checker('MainWindowTitle'))
PROC_ATTRS.add_attr('name', '', wait=(pop,), get=())
PROC_ATTRS.add_class_attr('Process', 'name', wait=attr_checker('ProcessName'), get=attr_reader('ProcessName'))
PROC_ATTRS.add_attr('re_name', '', wait=(pop_re,))
PROC_ATTRS.add_class_attr('Process', 're_name', wait=re_checker('ProcessName'))


PROC_FILTER_PARAMS = (
    (pop,), {
       'negative': (('negative', fixed_val(True)),),
       'single': (('single', fixed_val(True)),),
       'none': (('none', fixed_val(True)),),
       'number': (('number', pop_type(int)),),
       'assert': (('_assert', fixed_val(True)),),
    }
)

def _negate(flag, f):
    """
    >>> f = lambda x: x
    >>> _negate(True, f)(True), _negate(True, f)(False), _negate(False, f)(True), _negate(False, f)(False)
    (False, True, True, False)
    """
    def _n(*a, **kw):
        return not f(*a, **kw) if flag else f(*a, **kw)
    return _n

@robot_args(PROC_FILTER_PARAMS, PROC_ATTRS, insert_attr_dict=True)
def proc_filter(pli, none=False, number=None, single=False, _assert=False, negative=False, attributes={}, attr_dict=None):
    li = list(pli)
    attr_filters = attributes.get('wait', {})
    for attr, params in attr_filters.iteritems():
        li = [item for item in li if attr_dict.action(item, attr, 'wait', params)]

    if negative:
        li = filter(lambda v: v not in li, pli)
    ok, li, msg = result_modifier(li, none=none, single=single, number=number)

    if not isinstance(pli, list) and isinstance(li, list):
        if len(li):
            li = li[0]
        else:
            li = None

    if not ok:
        if _assert:
            logging.error('Proc Filter failed: %s' % msg)
            raise IronbotException('Proc Filter failed: %s' % msg)
        logging.warning('Proc Filter failed: %s' % msg)

    return li


APP_STATE_PARAMS = (
    (pop,), {
       'running': (('running', fixed_val(True)),),
       'not_running': (('running', fixed_val(False)),),
       'kill': (('running', fixed_val(None)),),
       'timeout': (('timeout', pop_type(Delay)),),
       'assert': (('_assert', fixed_val(True)),),
       'any': (('any', fixed_val(True)),),
       'all': (('all', fixed_val(True)),),
       'single': (('single', fixed_val(True)),),
       'none': (('none', fixed_val(True)),),
       'number': (('number', pop_type(int)),),
    }
)


@robot_args(APP_STATE_PARAMS)
def app_state(app, running=True, timeout=Delay('0s'), any=False, all=False, single=False, none=False, _assert=False, number=None):
    """
    Test
    :param app: required, positional -- an application object;
    :param running: an optional flag -- the result is True if the app is running;
    :param not_running: an optional flag -- the result is True if the app is not running;
    :param kill: an optional flag -- same as not_running plus kills the app after waiting;
    :param assert: an optional flag -- fail keyword on failure;
    :param timeout: optional, followed by a delay value, e.g. *10s -- wait for the desired state.
    :return: True if the app state at the end of waiting is as desired, otherwise False
    """
    src_app = app
    if not isinstance(src_app, list):
        app = [app]

    kill = running is None
    running = bool(running)

    prefer_bool = all or any or single or none or not isinstance(src_app, list)

    for _ in waiting_iterator(timeout):
        res_list = []
        for a in app:
            res_list.append(bool(a.HasExited) != bool(running))
        ok, res, msg = result_modifier(res_list, src_list=src_app, any=any, all=all, single=single, none=none, number=number, prefer_bool=prefer_bool)
        if ok:
            break

    if kill:
        for a in app:
            if not a.HasExited:
                logging.warning('Killing an application')
                a.Dispose()
    if ok:
        return res
    if _assert:
        logging.error('App State failed: %s' % msg)
        raise IronbotTimeoutException('App State failed: %s' % msg)
    logging.warning('App State failed: %s' % msg)
    return res


APP_ATTACH_PARAMS = (
    (pop,), {
       'suite_teardown': (('teardown', fixed_val('suite')),),
       'test_teardown': (('teardown', fixed_val('test')),),
    }
)


@robot_args(APP_ATTACH_PARAMS)
def app_attach(processes, teardown=None):
    global TEST_CONTROLLED_APPS, SUITE_CONTROLLED_APPS
    single = not isinstance(processes, list)
    if single:
        processes = [processes]
    apps = [Application.Attach(p) for p in processes]
    if teardown == 'test':
        TEST_CONTROLLED_APPS += apps
    elif teardown == 'suite':
        SUITE_CONTROLLED_APPS += apps
    if single:
        return apps[0]
    return apps


WND_ATTRS = AttributeDict()
WND_ATTRS.add_attr('id', '', wait=(pop,), get=())
WND_ATTRS.add_class_attr('Window', 'id', wait=attr_checker('Id'), get=lambda x: x.Id)
WND_ATTRS.add_attr('re_id', '', wait=(pop_re,),)
WND_ATTRS.add_class_attr('Window', 're_id', wait=re_checker('Id'))
WND_ATTRS.add_attr('title', '', wait=(pop,), get=())
WND_ATTRS.add_class_attr('Window', 'title', wait=attr_checker('Name'), get=lambda x: x.Name)
WND_ATTRS.add_attr('re_title', '', wait=(pop_re,))
WND_ATTRS.add_class_attr('Window', 're_title', wait=re_checker('Name'))
WND_ATTRS.add_attr('automation_id', '', wait=(pop,), get=())
WND_ATTRS.add_class_attr('Window', 'automation_id', wait=check_aid, get=get_aid)
WND_ATTRS.add_attr('re_automation_id', '', wait=(pop_re,))
WND_ATTRS.add_class_attr('Window', 're_automation_id', wait=re_check_aid)
WND_ATTRS.add_attr('closed', '', wait=(), get=())
WND_ATTRS.add_class_attr('Window', 'closed', wait=lambda w: w.IsClosed, get=lambda w: w.IsClosed)
WND_ATTRS.add_attr('not_closed', '', wait=(), get=())
WND_ATTRS.add_class_attr('Window', 'not_closed', wait=lambda w: not w.IsClosed, get=lambda w: not w.IsClosed)
WND_ATTRS.add_attr('active', '', wait=(), get=())
WND_ATTRS.add_class_attr('Window', 'active', wait=lambda w: w.IsActive, get=lambda w: w.IsActive)
WND_ATTRS.add_attr('not_active', '', wait=(), get=())
WND_ATTRS.add_class_attr('Window', 'not_active', wait=lambda w: not w.IsActive, get=lambda w: not w.IsActive)
WND_ATTRS.add_attr('close', '', do=())
WND_ATTRS.add_class_attr('Window', 'close', do=lambda w: w.Close())
WND_ATTRS.add_attr('wait_while_busy', '', do=())
WND_ATTRS.add_class_attr('Window', 'wait_while_busy', do=lambda w: w.WaitWhileBusy())


WND_FILTER_PARAMS = (
    (pop,), {
       'negative': (('negative', fixed_val(True)),),

       'single': (('single', fixed_val(True)),),
       'number': (('number', pop_type(int)),),
       'none': (('none', fixed_val(True)),),
       'assert': (('_assert', fixed_val(True)),),
    }
)


def _wnd_filter(wlist, single=False, negative=False, none=False, number=None, attributes={}, _assert=False, attr_dict=None):
    li = list(wlist)
    attr_filters = attributes.get('wait', {})

    for attr, params in attr_filters.iteritems():
        li = [item for item in li if attr_dict.action(item, attr, 'wait', params)]

    if negative:
        li = filter(lambda v: v not in li, wlist)

    ok, res, msg = result_modifier(li, src_list=wlist, none=none, single=single, number=number)
    if ok:
        return res
    if _assert:
        raise IronbotException('Wnd Filter failed: %s' % msg)

    logging.warning('Wnd Filter failed: %s' % msg)
    return res

wnd_filter = robot_args(WND_FILTER_PARAMS, WND_ATTRS, insert_attr_dict=True)(_wnd_filter)


WND_GET_PARAMS = (
    (), {
       'app': (('app', pop),),
       'parent': (('parent', pop),),
       'timeout': (('timeout', pop_type(Delay)),),
       'single': (('single', fixed_val(True)),),
       'number': (('number', pop_type(int)),),
       'none': (('none', fixed_val(True)),),
       'assert': (('_assert', fixed_val(True)),),
    }
)

@robot_args(WND_GET_PARAMS, WND_ATTRS, insert_attr_dict=True)
def wnd_get(app=None, parent=None, attr_dict=None, **kw):
    if app and parent:
        raise IronbotException("You may specify either 'app' or 'parent' parameter, not both")
    timeout = kw.get('timeout', None)
    if 'timeout' in kw:
        del kw['timeout']
    for _ in waiting_iterator(timeout):
        exc, res = None, None
        try:
            try:
                if app:
                    wnd_list = app.GetWindows()
                elif parent:
                    wnd_list = parent.ModalWindows()
                else:
                    wnd_list = Desktop.Instance.Windows()
            except:
                logging.error("Wnd Get: unable to obtain wnd_list: %s" % format_exc())
                wnd_list = []
            res = _wnd_filter(wnd_list, attr_dict=attr_dict, **kw)
        except Exception, e:
            exc = e
        if res:
            return res
    if isinstance(exc, Exception):
        raise exc
    return res

"""
def wnd_close(li):
    wli = li
    if not isinstance(li, list):
        wli = [li]
    for w in wli:
        w.Close()
    return li
"""

ADDITIONAL_CRITERIAS = {
    'text': lambda v: lambda c: c.AndByText(v),
    'automation_id':  lambda v: lambda c: c.AndByAutomationId(v),
    'id':  lambda v: lambda c: c.AndById(v),
}


CONTROL_TYPES = {
    'all': None,
    'button': Button,
    'edit': TextBox,
    'menu': Menu,
    'list': ListBox,
    'listitem': ListItem,
    #'edit': ControlType.Edit,
}


CTL_ATTRS = AttributeDict()
CTL_ATTRS.add_attr('id', '', wait=(pop,), get=())
CTL_ATTRS.add_class_attr('UIItem', 'id', wait=attr_checker('Id'), get=lambda x: x.Id)
CTL_ATTRS.add_attr('re_id', '', wait=(pop_re,))
CTL_ATTRS.add_class_attr('UIItem', 're_id', wait=re_checker('Id'))
CTL_ATTRS.add_attr('name', '', wait=(pop,), get=lambda x: x.Name)
CTL_ATTRS.add_class_attr('UIItem', 'name', wait=attr_checker('Name'))
CTL_ATTRS.add_attr('re_name', '', wait=(pop_re,))
CTL_ATTRS.add_class_attr('UIItem', 're_name', wait=re_checker('Name'))
CTL_ATTRS.add_attr('automation_id', '', wait=(pop,), get=lambda x: x.AutomationElement.GetCurrentPropertyValue(AutomationElement.AutomationIdProperty))
CTL_ATTRS.add_class_attr('UIItem', 'automation_id', wait=check_aid)
CTL_ATTRS.add_attr('re_automation_id', '', wait=(pop_re,))
CTL_ATTRS.add_class_attr('UIItem', 're_automation_id', wait=re_check_aid)
CTL_ATTRS.add_attr('enabled', '', get=(), wait=())
CTL_ATTRS.add_class_attr('UIItem', 'enabled', get=lambda x: x.Enabled, wait=lambda x: x.Enabled)
CTL_ATTRS.add_attr('disabled', '', get=(), wait=())
CTL_ATTRS.add_class_attr('UIItem', 'disabled', get=lambda x: not x.Enabled, wait=lambda x: not x.Enabled)


CTL_ATTRS.add_attr('click', '', do=(), get=())
CTL_ATTRS.add_class_attr('UIItem', 'click', do=lambda x: x.Click(), get=lambda x: x.Click())
CTL_ATTRS.add_attr('dclick', '', do=(), get=())
CTL_ATTRS.add_class_attr('UIItem', 'dclick', do=lambda x: x.DoubleClick(), get=lambda x: x.DoubleClick())
CTL_ATTRS.add_attr('rclick', '', do=(), get=())
CTL_ATTRS.add_class_attr('UIItem', 'rclick', do=lambda x: x.RightClick(), get=lambda x: x.RightClick())

CTL_ATTRS.add_attr('visible', '', get=())
CTL_ATTRS.add_class_attr('UIItem', 'visible', get=lambda x: x.Visible())
CTL_ATTRS.add_attr('focus', '', do=(), get=())
CTL_ATTRS.add_class_attr('UIItem', 'focus', do=lambda x: x.Focus(), get=lambda x: x.IsFocussed)

CTL_ATTRS.add_attr('text', '', get=(), set=(pop,))
CTL_ATTRS.add_class_attr('TextBox', 'text', get=lambda x: x.Text, set=lambda x, v: setattr(x, 'Text', v))
CTL_ATTRS.add_class_attr('ListItem', 'text', get=lambda x: x.Text)

CTL_ATTRS.add_attr('items', '', get=())
CTL_ATTRS.add_class_attr('ListBox', 'items', get=lambda x: [i.Name for i in x.Items])

#def checked(x, i):
#    return x.IsChecked(i.Text)

#def check(x, item):
#    x.Check(item)

def listbox_get_selected_idx(x):
    for i, item in enumerate(x.Items):
        if item == x.SelectedItem:
            return i
    return -1

def listbox_select_idx(x, idx):
    x.Select(idx)

def listbox_get_selected(x):
    return x.SelectedItemText


CTL_ATTRS.add_attr('selected', '', get=(), set=(pop,))
CTL_ATTRS.add_class_attr('ListBox', 'selected', get=listbox_get_selected, set=listbox_select_idx)
CTL_ATTRS.add_attr('idx_selected', '', get=(), set=(pop_type(int),))
CTL_ATTRS.add_class_attr('ListBox', 'idx_selected', get=listbox_get_selected_idx, set=lambda x, i: x.Select(i))
CTL_ATTRS.add_attr('num_items', '', get=(), wait=(pop_type(int),))
CTL_ATTRS.add_class_attr('ListBox', 'num_items', get=lambda x: len(x.Items), wait=lambda x, n: n == len(x.Items))





CTL_ATTRS.add_attr('texts', '', get=(),)
CTL_ATTRS.add_class_attr('UIItem', 'texts', get=full_text)



CTL_ATTRS.add_attr('merged_texts', '', get=(),)
CTL_ATTRS.add_class_attr('UIItem', 'merged_texts', get=lambda x: '\n'.join(full_text(x)))


CTL_GET_PARAMS = (
    (pop,), {
       'parent': (('parent', pop),),
       'list':  (('src_li', pop),),
       'negative': (('negative', fixed_val(True)),),
       'timeout': (('timeout', pop_type(Delay)),),
       'index': (('index', pop_type(int)),),
       'single': (('single', fixed_val(True)),),
       'none': (('none', fixed_val(True)),),
       'number': (('number', pop_type(int)),),
       'assert': (('_assert', fixed_val(True)),),
})


@robot_args(CTL_GET_PARAMS, CTL_ATTRS, insert_attr_dict=True)
def ctl_get(c_type, parent=None, src_li=None, timeout=Delay('0s'), number=None, negative=False, single=False, none=False, _assert=False, index=None, attributes={}, attr_dict=None):
    ct = CONTROL_TYPES.get(c_type)
    if ct:
        criteria = SearchCriteria.ByControlType(CONTROL_TYPES.get(c_type))
    else:
        criteria = SearchCriteria.All
    attr_filters = attributes.get('wait', {})
    for _ in waiting_iterator(timeout):
        if parent:
            #logging.warning(repr(parent) + repr(dir(parent)))
            mult = parent.GetMultiple(criteria)
            li = [elem for elem in mult]
        elif src_li:
            li = list(src_li)

        for attr, params in attr_filters.iteritems():
            li = [item for item in li if attr_dict.action(item, attr, 'wait', params)]

        if negative:
            li = filter(lambda v: v not in li, src_li)

        ok, res, msg = result_modifier(li, src_list=src_li, single=single, none=none, number=number, index=index)
        if ok:
            return res
    if _assert:
        logging.error('Ctl Get failed: %s' % msg)
        raise IronbotException('Ctl Get failed: %s' % msg)
    logging.warning('Ctl Get failed: %s' % msg)
    return res


CTL_ATTR_PARAMS = ((pop,), {'timeout': (('timeout', pop_type(Delay)),), 'assert': (('_assert', fixed_val(True)),),})
WND_ATTR_PARAMS = CTL_ATTR_PARAMS
PROC_ATTR_PARAMS = CTL_ATTR_PARAMS


def _attr(controls, attributes, attr_dict, timeout=Delay('0s'), _assert=False):
    single = False
    ctls = controls
    if not isinstance(ctls, list):
        ctls = [ctls]
        single = True
    gets = attributes.get('get', {})
    sets = attributes.get('set', {})
    dos = attributes.get('do', {})
    waits = attributes.get('wait', {})

    get_keys = list(gets.keys())
    get_keys.sort()

    success = True


    for _ in waiting_iterator(timeout):
        #logging.warning("CHECKING %s" % repr(timeout.value))
        success = True
        for c in ctls:
            for a, p in waits.iteritems():
                if not attr_dict.action(c, a, 'wait', p):
                    success = False
        if success:
            break

    if not success:
        if _assert:
            raise IronbotTimeoutException('Error: Attribute timeout')
        logging.warning('Error: Attribute timeout')


    res = [(lambda li: li[0] if len(gets) == 1 else li)
           ([attr_dict.action(c, a, 'get', gets[a]) for a in get_keys]) for c in ctls]

    for a, p in dos.iteritems():
        for c in ctls:
            attr_dict.action(c, a, 'do', p)

    for a, p in sets.iteritems():
        for c in ctls:
            attr_dict.action(c, a, 'set', p)

    if single:
        return res[0]
    return res

ctl_attr = robot_args(CTL_ATTR_PARAMS, CTL_ATTRS, default_action='get', insert_attr_dict=True)(_attr)
wnd_attr = robot_args(WND_ATTR_PARAMS, WND_ATTRS, default_action='get', insert_attr_dict=True)(_attr)
proc_attr = robot_args(PROC_ATTR_PARAMS, PROC_ATTRS, default_action='get', insert_attr_dict=True)(_attr)