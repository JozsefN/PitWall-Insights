"""Browser interaction shared by native filters and the rich driver listbox."""
from playwright.sync_api import expect


def select_control(control, value=None, *, label=None, index=None, timeout=30000):
    if control.evaluate("node => node.tagName === 'SELECT'"):
        arguments = {"timeout": timeout}
        if value is not None:
            arguments["value"] = value
        if label is not None:
            arguments["label"] = label
        if index is not None:
            arguments["index"] = index
        return control.select_option(**arguments)
    control.click(timeout=timeout)
    popup = control.page.get_by_role("listbox", name=control.get_attribute("aria-label"), exact=True)
    options = popup.get_by_role("option")
    if index is not None:
        target = options.nth(index)
    elif label is not None:
        target = options.get_by_text(label, exact=True)
    else:
        values = options.evaluate_all("nodes => nodes.map(node => node.dataset.value)")
        assert value in values, (value, values)
        target = options.nth(values.index(value))
    target.click(timeout=timeout)
    expect(control).to_have_attribute("aria-expanded", "false")
