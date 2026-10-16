package arct

import (
	"context"
	"fmt"
	"iter"
	"strconv"
)

func (c *Client) Iterate(ctx context.Context, operation string, query Params) iter.Seq2[Result, error] {
	return func(yield func(Result, error) bool) {
		q := Params{}
		for k, v := range query {
			q[k] = v
		}
		if _, ok := q["per_page"]; !ok {
			q["per_page"] = 100
		}
		page := 1
		if n, ok := q["page"].(int); ok {
			page = n
		}
		for ; page <= 100000; page++ {
			q["page"] = page
			r, err := c.Call(ctx, operation, "", q, nil)
			if err != nil {
				yield(nil, err)
				return
			}
			items, _ := r["data"].([]any)
			if len(items) == 0 {
				return
			}
			for _, v := range items {
				item, ok := v.(map[string]any)
				if !ok {
					yield(nil, fmt.Errorf("invalid list item"))
					return
				}
				if !yield(Result(item), nil) {
					return
				}
			}
			pagination, _ := r["pagination"].(map[string]any)
			total, _ := strconv.Atoi(fmt.Sprint(pagination["total_pages"]))
			if total > 0 && page >= total {
				return
			}
		}
		yield(nil, fmt.Errorf("pagination exceeded API page limit"))
	}
}
