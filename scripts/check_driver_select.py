"""Exercise rich driver controls with touch, keyboard, missing data and clipping.

Requires Vite on :5173 and Playwright. Does not use or change backend data.
"""
import os
from playwright.sync_api import expect, sync_playwright
from filter_controls import select_control


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        page.goto(os.environ.get("PITWALL_FRONTEND_URL", "http://localhost:5173") + "/login")
        page.evaluate(r"""async () => {
          const source = await (await fetch('/src/main.tsx')).text();
          const React = (await import(source.match(/from "([^"]+\/react.js[^"]*)"/)[1])).default;
          const {createRoot} = (await import(source.match(/from "([^"]+\/react-dom_client.js[^"]*)"/)[1])).default;
          const {DriverSelect} = await import('/src/components/DriverSelect.tsx');
          const {driverOption} = await import('/src/components/driver-select-options.ts');
          const container = document.createElement('div'); document.body.append(container);
          container.style = 'position:fixed;right:0;bottom:8px;width:148px;height:100px;overflow:hidden;z-index:999';
          const root = createRoot(container);
          const rows = [
            {id:'16',car_number:'16',driver_name:'Charles Leclerc',driver_abbreviation:'LEC',team_color:'FFFFFF'},
            {id:'4',car_number:'4',driver_name:'Lando Norris',driver_abbreviation:'NOR',team_color:'FF8700'},
            {id:'1',car_number:'1',driver_name:'Max Verstappen',driver_abbreviation:'VER',team_color:'000000'}
          ];
          for (let i=5;i<=24;i++) if (i!==16) rows.push({id:String(i),car_number:String(i),driver_name:`Driver ${i}`,driver_abbreviation:'TST',team_color:'00D2BE'});
          function Fixture({empty,disabled}) {
            const [value,setValue] = React.useState('');
            return React.createElement(DriverSelect, {'aria-label':'Driver fixture',
              options:empty?[]:[{value:'',label:'All selected (22)'},...rows.map(entry=>driverOption(entry))],
              value,onChange:setValue,disabled});
          }
          window.mountFilter = (empty=false,disabled=false) => root.render(
            React.createElement(Fixture,{key:String(empty)+String(disabled),empty,disabled}));
          window.mountFilter();
        }""")
        control = page.get_by_role("combobox", name="Driver fixture")
        for theme in ["dark", "light"]:
            page.evaluate("theme => document.documentElement.dataset.theme = theme", theme)
            control.focus()
            for key in ["n", "o", "r", "Enter"]:
                control.press(key)
            expect(control).to_have_attribute("data-value", "4")
            for key in ["1", "6", "Enter"]:
                control.press(key)
            expect(control).to_have_attribute("data-value", "16")
            control.press("ArrowDown")
            expect(control).to_have_attribute("aria-expanded", "true")
            control.press("ArrowUp")
            control.press("Enter")
            expect(control).to_have_attribute("data-value", "16")
            control.tap()
            popup = page.get_by_role("listbox", name="Driver fixture")
            expect(popup).to_be_visible()
            box = popup.bounding_box()
            assert box["x"] >= 0 and box["x"] + box["width"] <= 390
            popup.get_by_role("option", name="#4 NOR Lando Norris", exact=True).tap()
            expect(control).to_have_attribute("data-value", "4")
            for key in ["Space", "End", "Enter"]:
                control.press(key)
            expect(control).to_have_attribute("data-value", "24")
            for key in ["Space", "Home", "Escape"]:
                control.press(key)
            expect(control).to_have_attribute("data-value", "24")
            control.tap()
            page.locator("h1").tap()
            expect(control).to_have_attribute("aria-expanded", "false")
            select_control(control, "4")
            expect(control).to_have_attribute("data-value", "4")
            select_control(control, index=0)
            expect(control).to_have_attribute("data-value", "")
            select_control(control, label="All selected (22)")
            expect(control).to_have_attribute("data-value", "")
            print(f"{theme}: typeahead, number search, arrow keys, selection/cancellation, touch and outside dismissal passed", flush=True)
        page.evaluate("window.mountFilter(false, true)")
        expect(control).to_be_disabled()
        page.evaluate("window.mountFilter(true, false)")
        expect(control).to_be_disabled()
        browser.close()
        print("Disabled and empty selector checks passed")


if __name__ == "__main__":
    main()
