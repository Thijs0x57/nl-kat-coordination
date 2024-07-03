from django_components import component


@component.register("modal")
class Modal(component.Component):
    template_name = "modal/template.html"

    def get_context_data(self, **kwargs):
        return {
            "dialogid": kwargs["dialogid"],
            "size": kwargs["size"],
        }

    class Media:
        js = "modal/script.js"
        css = "dist/components.css"
