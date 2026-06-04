window.addEventListener('load', function() {
    function hideSliderInputs() {
        document.querySelectorAll('.dash-range-slider-input').forEach(function(el) {
            el.style.cssText = 'display:none!important;width:0!important;height:0!important;padding:0!important;margin:0!important;border:none!important;overflow:hidden!important;';
        });
    }
    hideSliderInputs();
    new MutationObserver(hideSliderInputs).observe(document.body, {childList: true, subtree: true});
});
