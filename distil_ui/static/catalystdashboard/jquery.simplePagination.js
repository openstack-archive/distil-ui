/**
The MIT License (MIT)

Copyright (c) 2015 Sebastian Marulanda http://marulanda.me

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
 */

(function($) {

	$.fn.simplePagination = function(options) {
		var defaults = {
			perPage: 5,
			containerClass: '',
			containerID: 'pager',
			previousButtonClass: 'btn btn-default',
			nextButtonClass: 'btn btn-default',
			firstButtonClass: 'btn btn-default',
			lastButtonClass: 'btn btn-default',
			firstButtonText: 'First',
		    lastButtonText: 'Last',
			previousButtonText: 'Prev',
			nextButtonText: 'Next',
			currentPage: 1
		};

		var settings = $.extend({}, defaults, options);

		return this.each(function() {
		    $("#" + settings.containerID).remove();
			var $rows = $('tbody tr', this);
			var pages = Math.ceil($rows.length/settings.perPage);

			var container = document.createElement('div');
			container.id = settings.containerID;
            var bFirst = document.createElement('button');
			var bPrevious = document.createElement('button');
			var bNext = document.createElement('button');
            var bLast = document.createElement('button');
			var of = document.createElement('span');

			bPrevious.innerHTML = settings.previousButtonText;
			bNext.innerHTML = settings.nextButtonText;
			bFirst.innerHTML = settings.firstButtonText;
			bLast.innerHTML = settings.lastButtonText;

			container.className = settings.containerClass;
			bPrevious.className = settings.previousButtonClass;
			bNext.className = settings.nextButtonClass;
			bFirst.className = settings.firstButtonClass;
			bLast.className = settings.lastButtonClass;

			bPrevious.style.marginRight = '8px';
			bNext.style.marginLeft = '8px';
			bFirst.style.marginRight = '8px';
			bLast.style.marginLeft = '8px';
			container.style.textAlign = "center";
			container.style.marginBottom = '20px';

            container.appendChild(bFirst);
			container.appendChild(bPrevious);
			container.appendChild(of);
			container.appendChild(bNext);
            container.appendChild(bLast);

			$(this).after(container);

			update();

			$(bFirst).click(function() {
                settings.currentPage = 1;
				update();
			});

			$(bLast).click(function() {
                settings.currentPage = pages;
				update();
			});

			$(bNext).click(function() {
				if (settings.currentPage + 1 > pages) {
					settings.currentPage = pages;
				} else {
					settings.currentPage++;
				}

				update();
			});

			$(bPrevious).click(function() {
				if (settings.currentPage - 1 < 1) {
					settings.currentPage = 1;
				} else {
					settings.currentPage--;
				}

				update();
			});

			function update() {
				var from = ((settings.currentPage - 1) * settings.perPage) + 1;
				var to = from + settings.perPage - 1;

				if (to > $rows.length) {
					to = $rows.length;
				}

				$rows.hide();
				$rows.slice((from-1), to).show();

				of.innerHTML = from + ' to ' + to + ' of ' + $rows.length + ' entries';

				if ($rows.length <= settings.perPage) {
					$(container).hide();
				} else {
					$(container).show();
				}
			}
		});

	}

}(jQuery));
